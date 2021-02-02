
import requests
from urllib.parse import urlparse
import re
import logging
from tqdm.auto import tqdm
import os.path
from abc import ABC, abstractmethod
from fake_useragent import UserAgent
from queue import Queue
import threading
import time

# requests.packages.urllib3.disable_warnings()

logging.basicConfig(filename="log.txt", filemode="w",
                    format="%(levelname)s %(message)s", level=logging.DEBUG)


class ShutdownException(Exception):
    def __str__(self):
        return "Shutdown signal received"


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

    def download(self, target_dir='.', shutdown_flag: threading.Event = None):
        ua = UserAgent()
        headers = {'User-Agent': ua.chrome}
        response = requests.get(self.download_url, stream=True, headers=headers, verify=False)
        if isinstance(self.progress, tqdm):
            self.progress.desc = self.file_name
            self.progress.total = float(response.headers["Content-Length"])
            self.progress.unit = "b"
            self.progress.unit_scale = True
            self.progress.unit_divisor = self.chunk_size

        if self.file_name and os.path.isdir(target_dir):
            try:
                with open(os.path.join(target_dir, self.file_name), 'wb') as handle:
                    # for data in tqdm(response.iter_content(chunk_size=1024),
                    #                  unit="KiB", unit_scale=True, unit_divisor=1024, position=tqdmpos,
                    #                  total=ceil(int(response.headers["Content-Length"]) / 1024)):
                    for data in response.iter_content(chunk_size=self.chunk_size):
                        if shutdown_flag and isinstance(shutdown_flag, threading.Event) and shutdown_flag.isSet():
                            raise ShutdownException

                        size = handle.write(data)

                        if isinstance(self.progress, tqdm):
                            self.progress.update(size)

            except ShutdownException:
                logging.warning("Shutdown signal reeceived")
                return False

            except Exception as e:
                logging.error(f"{str(e)}")
                return False

            finally:
                response.close()
                logging.debug(f"'{self.url}' closed")
                if isinstance(self.progress, tqdm):
                    self.progress.close()
                    logging.debug(f"'{self.progress.desc}' closed")

        logging.debug(f"'{self.file_name}' downloaded")
        return True


class ZippyshareDownloader(Downloader):
    def __init__(self, url, *args, **kwargs):
        ua = UserAgent()
        headers = {'User-Agent': ua.chrome}
        self.response = requests.get(url, headers=headers, verify=False)
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
        response = requests.get(self.url, verify=False)
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
    # for disabling ssl verify warning
    requests.packages.urllib3.disable_warnings()

    filename = "urls.txt"

    with open(filename, "r") as _file:
        urllist = [i.strip() for i in _file.readlines() if i.strip() != ""]
    urllist = urllist[68:]
    # num_urllist = enumerate(urllist[49:])
    # num_urllist = enumerate(urllist)

    max_threads = 2

    url_que = Queue()
    done_que = Queue()
    error_que = Queue()

    threads = []

    shutdown_flag = threading.Event()

    def worker(progress_pos):
        while not url_que.empty() and not shutdown_flag.isSet():
            _url = url_que.get()

            progress = tqdm(position=progress_pos, mininterval=1)
            downloader = ZippyshareDownloader(_url, progress=progress)
            success = downloader.download(target_dir=".\\downloads", shutdown_flag=shutdown_flag)
            if success:
                done_que.put(downloader.file_name)
            else:
                error_que.put(downloader.file_name)

            # url_que.task_done()

    for url in urllist:
        url_que.put(url)

    for i in range(max_threads):
        thread = threading.Thread(target=worker, args=(i,), daemon=True)
        thread.start()
        threads.append(thread)
    try:
        not_finished = True

        while not_finished:
            time.sleep(1)

            if url_que.empty():
                not_finished = False
                for t in threads:
                    if t.is_alive():
                        not_finished = True
                        break

    except KeyboardInterrupt:
        shutdown_flag.set()
        for t in threads:
            t.join(5)
            logging.debug(f"'{t.name}' terminated")

    while not done_que.empty():
        logging.debug(f"Successfully downloaded: '{done_que.get()}'")
    while not error_que.empty():
        logging.error(f"Could not downloaded: '{error_que.get()}'")


if __name__ == '__main__':
    from colorama import init

    init()
    main()
