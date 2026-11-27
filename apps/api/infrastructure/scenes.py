from app.postgres import APIError

from application.scenes import SceneAlreadyRegistered, SceneLakeMissing, SceneStoreUnavailable


class PostgresScenes:
    def __init__(self, client):
        self.client = client

    def add(self, scene: dict) -> dict:
        try:
            result = self.client.schema("satellite").table("scenes").insert(scene).execute()
        except APIError as exc:
            if exc.code == "23505":
                raise SceneAlreadyRegistered from exc
            if exc.code == "23503":
                raise SceneLakeMissing from exc
            raise SceneStoreUnavailable from exc
        if not result.data:
            raise SceneStoreUnavailable
        return result.data[0]
