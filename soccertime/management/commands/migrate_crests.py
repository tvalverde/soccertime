import os
import shutil
import hashlib

from django.core.management.base import BaseCommand
from django.conf import settings
from soccertime.models import Team, gen_upload_to


def sha1_from_field(fieldfile):
    """Generate a SHA1 hash of the file content and preserve the extension."""
    hash_sha1 = hashlib.sha1()
    fieldfile.open('rb')
    for chunk in fieldfile.chunks():
        hash_sha1.update(chunk)
    fieldfile.close()

    ext = os.path.splitext(fieldfile.name)[1].lower()
    return f"{hash_sha1.hexdigest()}{ext}"


def remove_empty_dirs(path, stop_at):
    """Recursively remove empty parent directories up to stop_at (non-inclusive)."""
    while path != stop_at and os.path.isdir(path) and not os.listdir(path):
        os.rmdir(path)
        path = os.path.dirname(path)


class Command(BaseCommand):
    help = 'Migrate crest images to new hashed filename and nested directory structure'

    def handle(self, *args, **options):
        media_root = os.path.abspath(settings.MEDIA_ROOT)

        for team in Team.objects.exclude(crest__isnull=True).exclude(crest=''):
            old_path = team.crest.path

            if not os.path.exists(old_path) or os.path.getsize(old_path) == 0:
                self.stdout.write(f"[DELETE] Missing or empty file: {old_path}")
                team.crest.delete(save=True)
                remove_empty_dirs(os.path.dirname(old_path), media_root)
                continue

            # Generate SHA1-based filename
            hashed_filename = sha1_from_field(team.crest)
            new_rel_path = gen_upload_to(team, hashed_filename)
            new_path = os.path.join(media_root, new_rel_path)

            if os.path.abspath(old_path) == os.path.abspath(new_path):
                self.stdout.write(f"[SKIP] {hashed_filename} already in correct path.")
                continue

            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            shutil.move(old_path, new_path)

            team.crest.name = new_rel_path
            team.save(update_fields=["crest"])

            self.stdout.write(f"[MOVED] {old_path} -> {new_rel_path}")
            remove_empty_dirs(os.path.dirname(old_path), media_root)
