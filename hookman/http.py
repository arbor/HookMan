import aiohttp
from aiohttp import web
import asyncio
import ssl
import traceback
from urllib.parse import urlparse
import concurrent.futures
import json
import functools
import hookman.mapping as mapping

class HTTP:

    def __init__(self, version, loop, logger, http, formats, test, config_file, reload):

        """
        Constructor

        :param version: version of the tool
        :param loop: asyncio loop
        :param logger: logger instance
        :param http: http configuration
        :param formats: formats to use as templates
        :param test: test mode?
        :param config_file: configuration file
        :param reload: reload config every time?
        """
        self.logger = logger
        self.version = version
        self.http = http
        self.formats = formats
        self.test = test
        self.config_file = config_file
        self.reload = reload

        self.url = None
        self._process_arg("url", http)

        self.ssl_certificate = None
        self._process_arg("ssl_certificate", http)

        self.ssl_key = None
        self._process_arg("ssl_key", http)

        self.stopping = False

        # Set up mapping object

        self.mapping = mapping.Mapping(self.logger)

        # Set up HTTP Client

        conn = aiohttp.TCPConnector()
        self.session = aiohttp.ClientSession(connector=conn)

        try:
            url = urlparse(self.url)

            net = url.netloc.split(":")
            self.host = net[0]
            try:
                self.port = net[1]
            except IndexError:
                self.port = 80

            if self.host == "":
                raise ValueError("Invalid host for 'url'")

            self.logger.info("Running on port %s", self.port)

            self.app = web.Application()

            self.loop = loop
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

            if self.ssl_certificate is not None and self.ssl_key is not None:
                context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                context.load_cert_chain(self.ssl_certificate, self.ssl_key)
            else:
                context = None

            self.setup_http_routes()

            handler = self.app.make_handler()

            f = loop.create_server(handler, "0.0.0.0", int(self.port), ssl=context)
            loop.create_task(f)
            loop.create_task(self.main_loop())

        except:
            self.logger.warning('-' * 60)
            self.logger.warning("Unexpected error in HTTP module")
            self.logger.warning('-' * 60)
            self.logger.warning(traceback.format_exc())
            self.logger.warning('-' * 60)

    def stop(self):
        self.stopping = True

    async def main_loop(self):
        # Keep things running
        while not self.stopping:
            await asyncio.sleep(1)

    def _process_arg(self, arg, kwargs):
        if kwargs:
            if arg in kwargs:
                setattr(self, arg, kwargs[arg])

    def get_response(self, request, code, error):
        res = "<html><head><title>{} {}</title></head><body><h1>{} {}</h1>Error in API Call</body></html>".format(code, error, code, error)
        app = request.match_info.get('app', "system")
        if code == 200:
            self.logger.info("Call to %s: status: %s", app, code)
        else:
            self.logger.warning("Call to %s: status: %s, %s", app, code, error)
        return web.Response(body=res, status=code)

    async def index(self, request):
        res = "<html><head><title>HookMan</title></head><body><h1>Hookman</h1>Version {}</body></html>".format(self.version)
        return web.Response(body=res, content_type="text/html", status=200)

    async def decode_request(self, request):
        url = {}
        headers = {}
        payload = {}

        # URL Parts
        url["url"] = request.url
        url["version"] = request.version
        url["method"] = request.method
        url["scheme"] = request.scheme
        url["host"] = request.host
        url["remote"] = request.remote
        url["path"] = request.path
        url["query"] = {}
        for k, v in request.query.items():
            url["query"][k] = v

        # Headers
        for k, v in request.headers.items():
            headers[k] = v

        # Payload
        if request.can_read_body:
            try:
                body = await request.json()
                payload = body
            except json.decoder.JSONDecodeError:
                self.logger.warning("Unknown payload type")

        return {"url": url, "headers": headers, "payload": payload}

    async def send_hook(self, method, url, headers, payload):
        text = "OK"
        code = 200
        if self.test is True:
            self.logger.info('-' * 60)
            self.logger.info("Output Request")
            self.logger.info('-' * 60)
            self.logger.info("url=%s", url)
            self.logger.info("headers=%s", headers)
            self.logger.info("payload=%s", payload)
            self.logger.info('-' * 60)
        else:
            try:
                if method == "GET":
                    r = await self.session.get(url, headers=headers)
                elif method == "POST":
                    r = await self.session.post(url, headers=headers, json=payload)
                else:
                    return web.Response(status=400, text="Unknown or unsupported method")

                if r.status >= 200 and r.status <299:
                    status = 200
                else:
                    txt = await r.text()
                    code = 400
                    text = "Error calling remote hook: status={}, error={}".format(r.status, txt)
                    self.logger.warning(text)
            except:
                self.logger.warning('-' * 60)
                self.logger.warning("Unexpected error during send_hook()")
                self.logger.warning("Service: %s.%s.%s Arguments: %s",url)
                self.logger.warning('-' * 60)
                self.logger.warning(traceback.format_exc())
                self.logger.warning('-' * 60)
                code = 400
                text = "Unexpected Internal Error"

        return web.Response(status=code, text=text)

    async def format(self, request):

        if self.reload is True:
            #
            # Re-read config file
            #
            try:
                with open(self.config_file) as json_file:
                    config = json.load(json_file)

                self.formats = config["mappings"]
            except Exception as e:
                self.logger.warning("Error loading configuration file: {}".format(e))

        mapping = request.match_info.get('mapping', None)

        if mapping is None:
            return self.get_response(request, 404, "Format not found")
        if mapping not in self.formats:
            return self.get_response(request, 404, "Format {} not found".format(mapping))
        if "method" not in self.formats[mapping]:
            return self.get_response(request, 400, "Missing request in format {}".format(mapping))

        incoming = await self.decode_request(request)

        if self.test is True:
            self.logger.info('-' * 60)
            self.logger.info("Input Parameters")
            self.logger.info('-' * 60)
            self.logger.info(incoming)
            self.logger.info('-' * 60)


        # Run mapping in an executor as it may be time intensive
        completed, pending = await asyncio.wait(
            [self.loop.run_in_executor(self.executor, functools.partial(self.mapping.map, self.formats[mapping], incoming))])
        future = list(completed)[0]
        new_url, new_headers, new_payload = future.result()

        response = await self.send_hook(self.formats[mapping]["method"], new_url, new_headers, new_payload)

        return response

    def setup_http_routes(self):
        self.app.router.add_get('/{mapping}', self.format)
        self.app.router.add_post('/{mapping}', self.format)
        self.app.router.add_get('/', self.index)


