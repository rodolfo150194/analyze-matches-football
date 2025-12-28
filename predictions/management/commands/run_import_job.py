"""
Internal command to run import job in background thread
DO NOT call directly - use start_import_view()
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from predictions.models import ImportJob
import io
import traceback
import threading
import time


class LogCapturingStringIO(io.StringIO):
    """StringIO that captures output and flushes periodically to database"""
    def __init__(self, job_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_id = job_id
        self.log_lines = []
        self.lock = threading.Lock()
        self.running = True

        # Start periodic flush thread
        self.flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self.flush_thread.start()

    def write(self, s):
        """Override write to capture logs"""
        super().write(s)
        # Accumulate logs in thread-safe way
        if s.strip():
            with self.lock:
                self.log_lines.append(s.strip())

    def _periodic_flush(self):
        """Periodically flush logs to database (every 2 seconds)"""
        while self.running:
            time.sleep(2)
            self.flush_logs_to_db()

    def flush_logs_to_db(self):
        """Write accumulated logs to database"""
        with self.lock:
            if not self.log_lines:
                return

            lines_to_write = self.log_lines.copy()
            self.log_lines.clear()

        # Write to DB outside the lock
        try:
            job = ImportJob.objects.get(pk=self.job_id)
            for line in lines_to_write:
                job.append_log(line)
        except ImportJob.DoesNotExist:
            pass

    def close(self):
        """Stop periodic flush and write remaining logs"""
        self.running = False
        if self.flush_thread.is_alive():
            self.flush_thread.join(timeout=1)
        self.flush_logs_to_db()
        super().close()


class Command(BaseCommand):
    help = 'Internal: Run import job in background'

    def add_arguments(self, parser):
        parser.add_argument('--job-id', type=int, required=True)

    def handle(self, *args, **options):
        job_id = options['job_id']

        try:
            job = ImportJob.objects.get(pk=job_id)
        except ImportJob.DoesNotExist:
            self.stderr.write(f"Job {job_id} not found")
            return

        # Update status to running
        job.status = 'running'
        job.started_at = timezone.now()
        job.save()

        # Create custom stdout that captures to database
        captured_stdout = LogCapturingStringIO(job_id)

        try:
            # Build command arguments
            cmd_args = [
                '--competitions', job.competitions,
                '--seasons', job.seasons,
                '--job-id', str(job_id),  # Pass job_id for progress tracking
            ]

            if job.import_teams and job.import_matches and job.import_players and job.import_standings:
                cmd_args.append('--all-data')
            else:
                if job.import_teams:
                    cmd_args.append('--teams-only')
                if job.import_matches:
                    cmd_args.append('--matches-only')
                if job.import_players:
                    cmd_args.append('--players-only')
                if job.import_standings:
                    cmd_args.append('--standings-only')

            if job.force:
                cmd_args.append('--force')
            if job.dry_run:
                cmd_args.append('--dry-run')

            # Run the actual import command
            # Note: stdout capturing happens through LogCapturingStringIO
            call_command('import_sofascore_complete', *cmd_args, stdout=captured_stdout, stderr=captured_stdout)

            # Close stream (stops periodic flush and writes remaining logs)
            captured_stdout.close()

            # Mark as completed
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.progress_percentage = 100
            job.append_log('[SUCCESS] Import completed successfully')
            job.save()

        except Exception as e:
            # Close stream (even on failure)
            captured_stdout.close()

            # Mark as failed
            job.status = 'failed'
            job.completed_at = timezone.now()
            job.error_message = str(e)
            job.append_log(f'[ERROR] Import failed: {str(e)}')
            job.append_log(traceback.format_exc())
            job.save()
