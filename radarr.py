import httpx

TIMEOUT = 15.0


class RadarrError(Exception):
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class RadarrClient:
    def __init__(self, config: dict):
        scheme = "https" if config.get("RADARR_SSL") else "http"
        host = config["RADARR_HOST"]
        port = config["RADARR_PORT"]
        base = config.get("RADARR_URL_BASE", "").strip("/")
        prefix = f"/{base}" if base else ""
        self._base_url = f"{scheme}://{host}:{port}{prefix}/api/v3"
        self._headers = {"X-Api-Key": config["RADARR_API_KEY"]}
        self._auth = None
        if config.get("RADARR_USERNAME") and config.get("RADARR_PASSWORD"):
            self._auth = (config["RADARR_USERNAME"], config["RADARR_PASSWORD"])

    async def _get(self, path: str, params: dict = None) -> list | dict:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, auth=self._auth) as client:
                r = await client.get(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    params=params,
                )
                r.raise_for_status()
                return r.json()
        except httpx.HTTPStatusError as e:
            raise RadarrError(str(e), status_code=e.response.status_code) from e
        except httpx.HTTPError as e:
            raise RadarrError(str(e)) from e

    async def _post(self, path: str, data: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, auth=self._auth) as client:
                r = await client.post(
                    f"{self._base_url}{path}",
                    headers=self._headers,
                    json=data,
                )
                r.raise_for_status()
                return r.json()
        except httpx.HTTPStatusError as e:
            raise RadarrError(str(e), status_code=e.response.status_code) from e
        except httpx.HTTPError as e:
            raise RadarrError(str(e)) from e

    async def search_movies(self, query: str) -> list:
        return await self._get("/movie/lookup", {"term": query})

    async def get_quality_profiles(self) -> list:
        return await self._get("/qualityprofile")

    async def get_root_folders(self) -> list:
        return await self._get("/rootfolder")

    async def add_movie(
        self,
        movie: dict,
        quality_profile_id: int,
        root_folder: str,
        monitored: bool = True,
        search_now: bool = True,
    ) -> dict:
        return await self._post("/movie", {
            "title": movie["title"],
            "qualityProfileId": quality_profile_id,
            "titleSlug": movie["titleSlug"],
            "images": movie.get("images", []),
            "tmdbId": movie["tmdbId"],
            "year": movie.get("year", 0),
            "rootFolderPath": root_folder,
            "monitored": monitored,
            "addOptions": {"searchForMovie": search_now},
        })

    async def get_library(self) -> list:
        return await self._get("/movie")

    async def get_calendar(self, start: str, end: str) -> list:
        return await self._get("/calendar", {"start": start, "end": end})

    async def _command(self, name: str) -> dict:
        return await self._post("/command", {"name": name})

    async def rss_sync(self) -> dict:
        return await self._command("RssSync")

    async def wanted_search(self) -> dict:
        return await self._command("MissingMoviesSearch")

    async def refresh_library(self) -> dict:
        return await self._command("RefreshMovie")
