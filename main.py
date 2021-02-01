
import concurrent.futures as cf
import requests
from urllib.parse import urlparse
import re
import logging
from tqdm.auto import tqdm
import os.path
from abc import ABC, abstractmethod
from fake_useragent import UserAgent


class Downloader(ABC):
    @abstractmethod
    def __init__(self, url, chunksize=1024, progress: tqdm = None):
        self.url = url
        self.chunk_size = chunksize
        self.progress = progress
        self.file_name = self._get_file_name()
        self.download_url = self._get_download_url()

    @abstractmethod
    def _get_file_name(self) -> str:
        return ""

    @abstractmethod
    def _get_download_url(self) -> str:
        return ""

    def download(self, target_dir='.'):
        response = requests.get(self.download_url, stream=True)
        if isinstance(self.progress, tqdm):
            self.progress.desc = self.file_name
            self.progress.total = float(response.headers["Content-Length"])
            self.progress.unit = "b"
            self.progress.unit_scale = True
            self.progress.unit_divisor = self.chunk_size

        if self.file_name and os.path.isdir(target_dir):
            with open(os.path.join(target_dir, self.file_name), 'wb') as handle:
                # for data in tqdm(response.iter_content(chunk_size=1024),
                #                  unit="KiB", unit_scale=True, unit_divisor=1024, position=tqdmpos,
                #                  total=ceil(int(response.headers["Content-Length"]) / 1024)):
                try:
                    for data in response.iter_content(chunk_size=self.chunk_size):
                        size = handle.write(data)
                        if isinstance(self.progress, tqdm):
                            self.progress.update(size)
                except KeyboardInterrupt:
                    response.close()
                    if isinstance(self.progress, tqdm):
                        self.progress.close()
                    return False
        return True


class ZippyshareDownloader(Downloader):
    def __init__(self, url, *args, **kwargs):
        ua = UserAgent()
        headers = {'User-Agent': ua.chrome}
        self.response = requests.get(url, headers=headers)
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
    logging.basicConfig(filename="log.txt", filemode="w",
                        format="%(levelname)s %(message)s")

    filename = "urls.txt"

    with open(filename, "r") as _file:
        urllist = [i.strip() for i in _file.readlines()]

    urllist = urllist[28:]

    max_threads = 4
    active_threads = {}
    with cf.ThreadPoolExecutor(max_workers=max_threads) as e:
        for num, url in enumerate(urllist):
            progress = tqdm(position=num, mininterval=1)
            downloader = ZippyshareDownloader(url, progress=progress)
            future = e.submit(downloader.download, target_dir=".\\downloads")
            active_threads[future] = url

            while len(active_threads) == max_threads:
                finished = False
                while not finished:
                    try:
                        completed_future, running_futures = cf.wait(active_threads.keys(),
                                                                    return_when=cf.FIRST_COMPLETED,
                                                                    timeout=0.01)
                        if completed_future:
                            finished = True
                            finished_future = completed_future.pop()
                    except cf.TimeoutError:
                        pass
                    except KeyboardInterrupt:
                        e.shutdown(cancel_futures=True, wait=False)
                        logging.error(f"'Keyboard interrupt' on '{active_threads.get(finished_future)}'")
                        quit()
                try:
                    if finished_future.result() is True:
                        logging.info(f"'{active_threads.get(finished_future)}' successfully downloaded")
                except Exception as err:
                    logging.error(f"'{str(err)}' on '{active_threads.get(finished_future)}'")

                active_threads.pop(finished_future)


if __name__ == '__main__':
    from colorama import init

    init()
    main()
