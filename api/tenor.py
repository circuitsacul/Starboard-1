from aiohttp_requests import requests
import json
import asyncio

apikey = '010WJV3ZGAN2'


def _simplify(url):
    return url.replace('http://', '').replace('https://', '')


def get_gif_id(url: str):
    base_url = 'tenor.com/view/'
    url = _simplify(url.casefold())
    if not url.startswith(base_url):
        return None
    gif_name = url.replace(base_url, '')
    gif_id = gif_name.split('-')[-1]
    return gif_id


async def get_gif_url(gifid: str):
    r = await requests.get(
        f"https://api.tenor.com/v1/gifs?ids={gifid}&key={apikey}"
    )

    if r.status == 200:
        # load the GIFs using the urls for the smaller GIF sizes
        gifs = json.loads(await r.text())
        return gifs['results'][0]['media'][0]['gif']['url']
    else:
        return None


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    url = input("URL: ")
    gifid = get_gif_id(url)
    if gifid is None:
        print("That is not a tenor url!")
    else:
        gif_url = loop.run_until_complete(get_gif_url(gifid))
        print(f"GIF URL: {gif_url}")
