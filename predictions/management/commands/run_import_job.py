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


class LogCapturingStringIO(io.StringIO):
    """StringIO that also writes to ImportJob"""
    def __init__(self, job_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_id = job_id

    def write(self, s):
        """Override write to capture and store in database"""
        super().write(s)

        # Append to ImportJob logs (thread-safe)
        if s.strip():  # Only write non-empty lines
            try:
                job = ImportJob.objects.get(pk=self.job_id)
                job.append_log(s.strip())
            except ImportJob.DoesNotExist:
                pass


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

            # Mark as completed
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.progress_percentage = 100
            job.append_log('[SUCCESS] Import completed successfully')
            job.save()

        except Exception as e:
            # Mark as failed
            job.status = 'failed'
            job.completed_at = timezone.now()
            job.error_message = str(e)
            job.append_log(f'[ERROR] Import failed: {str(e)}')
            job.append_log(traceback.format_exc())
            job.save()
