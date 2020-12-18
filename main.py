from concurrent.futures.thread import ThreadPoolExecutor

import requests
from urllib.parse import urlparse
import re
from tqdm.auto import tqdm
import os.path
from abc import ABC, abstractmethod


class Downloader(ABC):
    @abstractmethod
    def __init__(self, url, chunksize=1024, progress: tqdm = None):
        self.url = url
        self.chunk_size = chunksize
        self.progress = progress
        self.file_name = self._get_file_name()
        self.download_url = self._get_download_url()

    @abstractmethod
    def _get_file_name(self):
        return ""

    @abstractmethod
    def _get_download_url(self):
        return ""

    def download(self, target_dir='.'):
        response = requests.get(self.download_url, stream=True)
        if isinstance(self.progress, tqdm):
            self.progress.total = float(response.headers["Content-Length"])
            self.progress.unit = "b"
            self.progress.unit_scale = True
            self.progress.unit_divisor = self.chunk_size

        if self.file_name and os.path.isdir(target_dir):
            with open(os.path.join(target_dir, self.file_name), 'wb') as handle:
                # for data in tqdm(response.iter_content(chunk_size=1024),
                #                  unit="KiB", unit_scale=True, unit_divisor=1024, position=tqdmpos,
                #                  total=ceil(int(response.headers["Content-Length"]) / 1024)):
                for data in response.iter_content(chunk_size=self.chunk_size):
                    size = handle.write(data)
                    if isinstance(self.progress, tqdm):
                        self.progress.update(size)


class ZippyshareDownloader(Downloader):
    def __init__(self, url, *args, **kwargs):
        self.response = requests.get(url)
        self.dl_button_href = self._get_dl_button_href()
        super().__init__(url, *args, **kwargs)

    def _get_dl_button_href(self):
        match = re.search(r'document.getElementById\(\'dlbutton\'\).href = "(.*?)" \+ \((.*?)\) \+ "(.*?)";',
                          self.response.text)
        if match:
            return match.group(1) + str(eval(match.group(2))) + match.group(3)
        return None

    def _get_file_name(self):
        match = re.search("<title>Zippyshare.com - (.*?)</title>", self.response.text[:512])
        if match:
            title = match.group(1).split()[0].strip()
            return title
        return None

    def _get_download_url(self):
        parsed_url = urlparse(self.url)
        download_url = parsed_url.scheme + '://' + parsed_url.netloc + self.dl_button_href
        return download_url


class PixeldrainDownloader(Downloader):
    def __init__(self, url, *args, **kwargs):
        super().__init__(url, *args, **kwargs)

    def _get_file_name(self):
        response = requests.get(self.url)
        match = re.search("<title>(.*?)</title>", response.text[:512])
        if match:
            title = match.group(1).split()[0].strip()
            return title
        return None

    def _get_download_url(self):
        parsed_url = urlparse(self.url)
        file_id = parsed_url.path.split('/')[-1]
        download_url = parsed_url.scheme + '://' + '/'.join([parsed_url.netloc, "api/file", file_id]) + "?download"
        return download_url


def main():
    # url = "https://pixeldrain.com/u/KtDbn3kD"
    # url = "https://www54.zippyshare.com/v/TxFPnFPu/file.html"
    # downloader = FileDownloader(url)
    # progress = tqdm()
    # downloader = ZippyshareDownloader(url, progress=progress)
    # print(downloader.download_url)
    # print(downloader.file_name)
    # downloader.download()

    url_list = ["https://www54.zippyshare.com/v/avWW6TGd/file.html",
                "https://www7.zippyshare.com/v/i1OTOQGh/file.html",
                "https://www79.zippyshare.com/v/H1P2p58m/file.html",
                "https://www52.zippyshare.com/v/TVHw5L1E/file.html"]
    with ThreadPoolExecutor(max_workers=4) as e:
        for num, url in enumerate(url_list):
            progress = tqdm(position=num, ncols=80, mininterval=1)
            downloader = ZippyshareDownloader(url, progress=progress)
            e.submit(downloader.download)


if __name__ == '__main__':
    from colorama import init

    init()
    main()
