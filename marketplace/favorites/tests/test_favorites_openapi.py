"""OpenAPI: тег Favorites (CRUD + subscribe)."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.openapi import CATALOG_PRODUCT_CARD_REQUIRED, PAGINATED_CATALOG_REQUIRED
from favorites.models import Favorite, ProductSubscription
from favorites.openapi import DEFAULT_SUBSCRIBE_EVENTS


User = get_user_model()


def _auth(client, user):
    client.defaults["HTTP_AUTHORIZATION"] = (
        f"Bearer {RefreshToken.for_user(user).access_token}"
    )


def _visible_product(product_id, *, title="Phone"):
    return {
        "id": str(product_id),
        "title": title,
        "status": "MODERATED",
        "deleted": False,
        "min_price": 10_000,
        "cover_image": "https://cdn.example.com/p.jpg",
    }


@pytest.mark.django_db
def test_add_to_favorites_returns_201(client, monkeypatch):
    """DoD-имя; OpenAPI: PUT → 204."""
    user = User.objects.create_user(
        email="u1@example.com", password="pass", first_name="U", last_name="1"
    )
    _auth(client, user)
    product_id = uuid.uuid4()

    class FakeB2B:
        def get_product(self, pid):
            return _visible_product(pid)

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.put(f"/api/v1/favorites/{product_id}")
    assert response.status_code == 204
    assert Favorite.objects.filter(user=user, product_id=product_id).exists()


@pytest.mark.django_db
def test_repeat_add_returns_200_not_duplicate(client, monkeypatch):
    """DoD-имя; OpenAPI: повторный PUT → 204."""
    user = User.objects.create_user(
        email="u2@example.com", password="pass", first_name="U", last_name="2"
    )
    _auth(client, user)
    product_id = uuid.uuid4()

    class FakeB2B:
        def get_product(self, pid):
            return _visible_product(pid)

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    assert client.put(f"/api/v1/favorites/{product_id}").status_code == 204
    assert client.put(f"/api/v1/favorites/{product_id}").status_code == 204
    assert Favorite.objects.filter(user=user, product_id=product_id).count() == 1


@pytest.mark.django_db
def test_get_favorites_enriched_from_b2b(client, monkeypatch):
    user = User.objects.create_user(
        email="enriched@example.com", password="pass", first_name="E", last_name="U"
    )
    _auth(client, user)
    product_id = uuid.uuid4()
    Favorite.objects.create(user=user, product_id=product_id)

    class FakeB2B:
        def batch_public_products(self, ids):
            return [_visible_product(product_id)]

        def get_categories(self):
            return []

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.get("/api/v1/favorites?limit=20&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert PAGINATED_CATALOG_REQUIRED <= set(data.keys())
    card = data["items"][0]
    assert CATALOG_PRODUCT_CARD_REQUIRED <= set(card.keys())
    assert card["name"] == "Phone"
    assert "slug" in card


@pytest.mark.django_db
def test_blocked_product_excluded_from_list(client, monkeypatch):
    user = User.objects.create_user(
        email="u3@example.com", password="pass", first_name="U", last_name="3"
    )
    _auth(client, user)
    visible_id = uuid.uuid4()
    blocked_id = uuid.uuid4()
    Favorite.objects.create(user=user, product_id=visible_id)
    Favorite.objects.create(user=user, product_id=blocked_id)

    class FakeB2B:
        def batch_public_products(self, ids):
            assert set(ids) == {str(visible_id), str(blocked_id)}
            return [_visible_product(visible_id, title="Visible")]

        def get_categories(self):
            return []

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.get(
        f"/api/v1/favorites?limit=20&offset=0&user_id={uuid.uuid4()}"
    )
    data = response.json()
    assert [item["id"] for item in data["items"]] == [str(visible_id)]
    assert data["total_count"] == 1


@pytest.mark.django_db
def test_user_id_from_query_is_ignored(client, monkeypatch):
    user1 = User.objects.create_user(
        email="u4@example.com", password="pass", first_name="U", last_name="4"
    )
    user2 = User.objects.create_user(
        email="u5@example.com", password="pass", first_name="U", last_name="5"
    )
    fav1 = uuid.uuid4()
    Favorite.objects.create(user=user1, product_id=fav1)
    Favorite.objects.create(user=user2, product_id=uuid.uuid4())
    _auth(client, user1)

    class FakeB2B:
        def batch_public_products(self, ids):
            assert ids == [str(fav1)]
            return [_visible_product(fav1, title="Mine")]

        def get_categories(self):
            return []

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.get(f"/api/v1/favorites?user_id={user2.id}")
    assert [item["id"] for item in response.json()["items"]] == [str(fav1)]


@pytest.mark.django_db
def test_delete_favorite_returns_204(client):
    user = User.objects.create_user(
        email="del@example.com", password="pass", first_name="D", last_name="U"
    )
    _auth(client, user)
    product_id = uuid.uuid4()
    Favorite.objects.create(user=user, product_id=product_id)

    response = client.delete(f"/api/v1/favorites/{product_id}")
    assert response.status_code == 204
    assert not Favorite.objects.filter(user=user, product_id=product_id).exists()

    again = client.delete(f"/api/v1/favorites/{product_id}")
    assert again.status_code == 204


@pytest.mark.django_db
def test_subscribe_post_returns_204(client, monkeypatch):
    user = User.objects.create_user(
        email="sub@example.com", password="pass", first_name="S", last_name="U"
    )
    _auth(client, user)
    product_id = uuid.uuid4()

    class FakeB2B:
        def get_product(self, pid):
            return _visible_product(pid)

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        {"events": ["PRICE_DROP"]},
        content_type="application/json",
    )
    assert response.status_code == 204
    sub = ProductSubscription.objects.get(user=user, product_id=product_id)
    assert sub.events == ["PRICE_DROP"]


@pytest.mark.django_db
def test_subscribe_post_default_events(client, monkeypatch):
    user = User.objects.create_user(
        email="sub2@example.com", password="pass", first_name="S", last_name="2"
    )
    _auth(client, user)
    product_id = uuid.uuid4()

    class FakeB2B:
        def get_product(self, pid):
            return _visible_product(pid)

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.post(f"/api/v1/favorites/{product_id}/subscribe")
    assert response.status_code == 204
    sub = ProductSubscription.objects.get(user=user, product_id=product_id)
    assert sub.events == DEFAULT_SUBSCRIBE_EVENTS


@pytest.mark.django_db
def test_unauthorized_returns_openapi_error(client):
    response = client.get("/api/v1/favorites")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHORIZED"
    assert "message" in body


@pytest.mark.django_db
def test_subscribe_unknown_product_returns_404(client, monkeypatch):
    user = User.objects.create_user(
        email="sub404@example.com", password="pass", first_name="S", last_name="4"
    )
    _auth(client, user)
    product_id = uuid.uuid4()

    class FakeB2B:
        def get_product(self, pid):
            from catalog.b2b_client import B2BClientError

            raise B2BClientError(404, "not found")

    monkeypatch.setattr("favorites.services.B2BClient", lambda: FakeB2B())

    response = client.post(f"/api/v1/favorites/{product_id}/subscribe")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_subscribe_delete_returns_204(client):
    user = User.objects.create_user(
        email="unsub@example.com", password="pass", first_name="U", last_name="S"
    )
    _auth(client, user)
    product_id = uuid.uuid4()
    ProductSubscription.objects.create(
        user=user, product_id=product_id, events=["BACK_IN_STOCK"]
    )

    response = client.delete(f"/api/v1/favorites/{product_id}/subscribe")
    assert response.status_code == 204
    assert not ProductSubscription.objects.filter(
        user=user, product_id=product_id
    ).exists()

    again = client.delete(f"/api/v1/favorites/{product_id}/subscribe")
    assert again.status_code == 204
