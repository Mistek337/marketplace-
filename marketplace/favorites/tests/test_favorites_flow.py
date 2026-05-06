import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from favorites.models import Favorite


User = get_user_model()


@pytest.mark.django_db
def test_add_to_favorites_returns_201(client, monkeypatch):
    user = User.objects.create_user(
        email="u1@example.com",
        password="pass",
        first_name="U",
        last_name="1",
    )
    token = str(RefreshToken.for_user(user).access_token)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    product_id = uuid.uuid4()

    class FakeB2BClient:
        def get_product(self, pid):
            assert str(pid) == str(product_id)
            return {"id": str(product_id), "title": "Phone", "images": [{"url": "img", "ordering": 0}], "skus": []}

    monkeypatch.setattr("favorites.views.B2BClient", lambda: FakeB2BClient())

    r = client.post(f"/api/v1/favorites/{product_id}", data={}, content_type="application/json")
    assert r.status_code == 201
    assert Favorite.objects.filter(user=user, product_id=product_id).count() == 1


@pytest.mark.django_db
def test_repeat_add_returns_200_not_duplicate(client, monkeypatch):
    user = User.objects.create_user(
        email="u2@example.com",
        password="pass",
        first_name="U",
        last_name="2",
    )
    token = str(RefreshToken.for_user(user).access_token)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    product_id = uuid.uuid4()

    class FakeB2BClient:
        def get_product(self, pid):
            return {"id": str(product_id), "title": "Phone", "images": [], "skus": []}

    monkeypatch.setattr("favorites.views.B2BClient", lambda: FakeB2BClient())

    r1 = client.post(f"/api/v1/favorites/{product_id}", data={}, content_type="application/json")
    r2 = client.post(f"/api/v1/favorites/{product_id}", data={}, content_type="application/json")
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert Favorite.objects.filter(user=user, product_id=product_id).count() == 1


@pytest.mark.django_db
def test_blocked_product_excluded_from_list(client, monkeypatch):
    user = User.objects.create_user(
        email="u3@example.com",
        password="pass",
        first_name="U",
        last_name="3",
    )
    token = str(RefreshToken.for_user(user).access_token)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    visible_id = uuid.uuid4()
    blocked_id = uuid.uuid4()
    Favorite.objects.create(user=user, product_id=visible_id)
    Favorite.objects.create(user=user, product_id=blocked_id)

    class FakeB2BClient:
        def get_products(self, *, limit, offset, category_id=None, filters=None, sort=None, search=None, ids=None):
            # имитируем поведение B2B витрины: блокированный не попадает в items
            assert ids is not None
            return {"items": [{"id": str(visible_id), "title": "Visible", "images": [], "skus": []}]}

    monkeypatch.setattr("favorites.views.B2BClient", lambda: FakeB2BClient())

    r = client.get("/api/v1/favorites?limit=20&offset=0&user_id=" + str(uuid.uuid4()))
    assert r.status_code == 200
    data = r.json()
    assert [it["product_id"] for it in data["items"]] == [str(visible_id)]
    assert data["total"] == 2


@pytest.mark.django_db
def test_user_id_from_query_is_ignored(client, monkeypatch):
    user1 = User.objects.create_user(
        email="u4@example.com",
        password="pass",
        first_name="U",
        last_name="4",
    )
    user2 = User.objects.create_user(
        email="u5@example.com",
        password="pass",
        first_name="U",
        last_name="5",
    )
    fav1 = uuid.uuid4()
    fav2 = uuid.uuid4()
    Favorite.objects.create(user=user1, product_id=fav1)
    Favorite.objects.create(user=user2, product_id=fav2)

    token = str(RefreshToken.for_user(user1).access_token)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    class FakeB2BClient:
        def get_products(self, *, limit, offset, category_id=None, filters=None, sort=None, search=None, ids=None):
            # Возвращаем только то, что запросили в ids (IDOR не должен дать ids от user2)
            assert ids == str(fav1)
            return {"items": [{"id": str(fav1), "title": "U1 item", "images": [], "skus": []}]}

    monkeypatch.setattr("favorites.views.B2BClient", lambda: FakeB2BClient())

    r = client.get("/api/v1/favorites?limit=20&offset=0&user_id=" + str(user2.id))
    assert r.status_code == 200
    data = r.json()
    assert [it["product_id"] for it in data["items"]] == [str(fav1)]
