import json
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from soccertime.models import Channel, Competition, Sport, Team

PUBLIC_PAGES = ["favorites", "agenda", "competitions", "channels"]


@pytest.mark.django_db
class TestAntiIndexing:
    def test_robots_txt_disallows_all(self, client):
        response = client.get("/robots.txt")

        assert response.status_code == 200
        assert "text/plain" in response.headers["Content-Type"]
        content = response.content.decode()
        assert "User-agent: *" in content
        assert "Disallow: /" in content

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_pages_carry_strict_noindex_meta_tag(self, client, page):
        response = client.get(reverse(page))

        assert response.status_code == 200
        html = response.content.decode()
        assert '<meta name="robots" content="noindex, nofollow, noarchive, nosnippet">' in html


@pytest.mark.django_db
class TestPwaConfiguration:
    def test_manifest_file_is_valid_json(self):
        manifest_path = Path(settings.BASE_DIR) / "soccertime/static/soccertime/manifest.json"
        assert manifest_path.exists()

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["name"] == "Soccertime - Agenda Deportiva"
        assert data["short_name"] == "Soccertime"
        assert data["display"] == "standalone"
        assert data["theme_color"] == "#0e0e0e"
        assert len(data["icons"]) >= 2

    def test_pwa_icons_exist_on_disk(self):
        img_dir = Path(settings.BASE_DIR) / "soccertime/static/soccertime/img"
        for filename in ["apple-touch-icon.png", "icon-192.png", "icon-512.png", "og-image.png"]:
            assert (img_dir / filename).exists(), f"Missing {filename}"

    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_pwa_link_tags_are_rendered_in_head(self, client, page):
        response = client.get(reverse(page))
        html = response.content.decode()

        assert 'rel="manifest"' in html
        assert 'rel="apple-touch-icon"' in html
        assert '<meta name="theme-color" content="#0e0e0e">' in html
        assert '<meta name="apple-mobile-web-app-capable" content="yes">' in html


@pytest.mark.django_db
class TestOpenGraphAndSocialCards:
    @pytest.mark.parametrize("page", PUBLIC_PAGES)
    def test_open_graph_base_tags_present_on_all_public_pages(self, client, page):
        response = client.get(reverse(page))
        html = response.content.decode()

        assert '<meta property="og:site_name" content="Soccertime">' in html
        assert '<meta property="og:type" content="website">' in html
        assert 'property="og:title"' in html
        assert 'property="og:description"' in html
        assert 'property="og:url"' in html
        assert 'property="og:image"' in html
        assert '<meta name="twitter:card" content="summary_large_image">' in html
        assert 'name="twitter:title"' in html
        assert 'name="twitter:description"' in html
        assert 'name="twitter:image"' in html

    def test_team_detail_page_renders_custom_og_title(self, client):
        team = Team.objects.create(name="Real Betis")
        response = client.get(reverse("team-events", args=[team.pk]))
        html = response.content.decode()

        assert '<meta property="og:title" content="Soccertime :: Real Betis">' in html
        assert '<meta name="twitter:title" content="Soccertime :: Real Betis">' in html

    def test_competition_detail_page_renders_custom_og_title(self, client):
        sport = Sport.objects.create(name="Fútbol")
        comp = Competition.objects.create(name="La Liga", sport=sport)
        response = client.get(reverse("competition-events", args=[comp.pk]))
        html = response.content.decode()

        assert '<meta property="og:title" content="Soccertime :: La Liga">' in html
        assert '<meta name="twitter:title" content="Soccertime :: La Liga">' in html

    def test_channel_detail_page_renders_custom_og_title(self, client):
        channel = Channel.objects.create(name="DAZN 1")
        response = client.get(reverse("channel-events", args=[channel.pk]))
        html = response.content.decode()

        assert '<meta property="og:title" content="Soccertime :: DAZN 1">' in html
        assert '<meta name="twitter:title" content="Soccertime :: DAZN 1">' in html

    def test_sport_detail_page_renders_custom_og_title(self, client):
        sport = Sport.objects.create(name="Baloncesto")
        response = client.get(reverse("sport-events", args=[sport.pk]))
        html = response.content.decode()

        assert '<meta property="og:title" content="Soccertime :: Baloncesto">' in html
        assert '<meta name="twitter:title" content="Soccertime :: Baloncesto">' in html
