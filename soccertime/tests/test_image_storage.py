"""The stored filename decides how nginx will label the file when it serves it back.

`save_image` used to take the extension from the source URL, so whoever served the image
chose it. Django does not object: `get_image_dimensions` answers `(None, None)` for
content it cannot parse rather than raising, so bytes that are not an image at all were
written into the media volume and returned from this site's own origin under whatever
extension the URL ended in. `.svg` is the sharp case — a legitimate image extension that
Pillow cannot decode, served as `image/svg+xml`, whose scripts a browser runs when the
file is opened directly.

Both halves of the name now come from the content: sha1 for the stem, the decoded format
for the extension.
"""

import hashlib
import io
import os

import pytest
from PIL import Image

from soccertime.images import ImageRejected, extension_for, read_image_format
from soccertime.models import Flag, Team

SVG_PAYLOAD = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'


def image_bytes(image_format="WEBP", size=(32, 24)):
    buffer = io.BytesIO()
    Image.new("RGB", size).save(buffer, format=image_format)
    buffer.seek(0)
    return buffer


class TestTheExtensionComesFromTheContent:
    @pytest.mark.parametrize(
        ("image_format", "expected"),
        [("WEBP", ".webp"), ("PNG", ".png"), ("JPEG", ".jpg"), ("GIF", ".gif")],
    )
    def test_each_stored_format_gets_its_own_extension(self, image_format, expected):
        assert extension_for(image_bytes(image_format)) == expected

    def test_the_url_has_no_say(self, db, settings, tmp_path):
        """The flag's `name` is the URL it came from, and it used to name the file too."""
        settings.MEDIA_ROOT = tmp_path
        flag = Flag.objects.create(name="https://evil.example/flag.html", display_name="Trampa")

        flag.save_flag(image_bytes("WEBP"))

        assert flag.image.name.endswith(".webp")
        assert ".html" not in flag.image.name

    def test_the_buffer_is_left_readable(self):
        """`save_image` hashes the bytes after asking for the extension."""
        buffer = image_bytes("PNG")
        original = buffer.getvalue()

        extension_for(buffer)

        assert buffer.read() == original


class TestContentThatIsNotAnImageIsRefused:
    def test_an_svg_payload_is_not_stored(self, db, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        flag = Flag.objects.create(name="https://evil.example/flag.svg", display_name="Trampa")

        with pytest.raises(ImageRejected):
            flag.save_flag(io.BytesIO(SVG_PAYLOAD))

        flag.refresh_from_db()
        assert not flag.image

    @pytest.mark.parametrize(
        "payload",
        [b"", b"<html><script>alert(1)</script></html>", b"\x89PNG\r\n\x1a\n" + b"rubbish" * 10, SVG_PAYLOAD],
    )
    def test_nothing_undecodable_gets_a_name(self, payload):
        with pytest.raises(ImageRejected):
            read_image_format(io.BytesIO(payload))

    def test_a_format_outside_the_allowlist_is_refused(self):
        """Decodable is not enough; it also has to be something this site serves."""
        with pytest.raises(ImageRejected, match="does not store"):
            read_image_format(image_bytes("BMP"))


class TestWhatWasAlreadyWorkingStillWorks:
    def test_the_name_stem_is_the_content_hash(self, db, settings, tmp_path):
        """Storage appends its own suffix when the name is taken, so this checks the stem.

        The hash is what makes the same bytes from two different URLs land in the same
        place, and what `gen_upload_to` shards the directories on.
        """
        settings.MEDIA_ROOT = tmp_path
        flag = Flag.objects.create(name="https://a.example/a.webp", display_name="A")
        buffer = image_bytes("WEBP")
        digest = hashlib.sha1(buffer.getvalue()).hexdigest()

        flag.save_flag(buffer)

        assert os.path.basename(flag.image.name).startswith(digest)
        assert flag.image.name.startswith(f"flags/{digest[:2]}/{digest[2:4]}/")

    def test_dimensions_are_recorded_from_the_buffer(self, db, settings, tmp_path):
        """Measured on the way in, so rendering never reopens the file."""
        settings.MEDIA_ROOT = tmp_path
        team = Team.objects.create(name="Con escudo")

        team.save_crest(image_bytes("PNG", size=(48, 24)))

        assert (team.crest_width, team.crest_height) == (48, 24)
        assert team.image_dimensions == (48, 24)
