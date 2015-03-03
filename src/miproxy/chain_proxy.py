# Extension to PyMiProxy
# by Richard McPherson
# based on code by Nadeem Douba 
# GPL

from proxy import *


# HTTPS to HTTP
class ClientMitmProxyHandler(ProxyHandler):

  def __init(self):
    ProxyHandler.__init__(self)
    self.chain_hostname = "localhost"
    self.chain_port = 8081
 
  # Overwrite _connect_to_host
  # Changes:
  #    Set next in proxy chain
  #    No ssl to next hop
  def _connect_to_host(self):
    # Get hostname and port to connect to
    if self.is_connect:
      self.hostname, self.port = self.path.split(':')
    else:
      u = urlparse(self.path)
      if u.scheme != 'http':
        raise UnsupportedSchemeException('Unknown scheme %s' % repr(u.scheme))
      self.hostname = u.hostname
      self.port = u.port or 80
      self.path = urlunparse(
        ParseResult(
          scheme='',
          netloc='',
          params=u.params,
          path=u.path or '/',
          query=u.query,
          fragment=u.fragment
        )
      )

      # Connect to destination
      self._proxy_sock = socket()
      self._proxy_sock.settimeout(10)
      self._proxy_sock.connect((self.chain_hostname, int(self.chain_port)))


# HTTP to HTTPS
class ServerMitmProxyHandler(ProxyHandler):

  # Overwrite _transition_to_ssl
  # Changes:
  #    Not wrapping socket with ssl
  def _transition_to_ssl(self):
        pass


# Make sure this code is working
class TestMitmProxyHandler(ProxyHandler):
  pass


def _main():
  from sys import argv
  proxy = None

  # check for argument
  if not argv[1]:
    print "Need one argument: [c/s/t]"
    return

  # launch client
  if argv[1].lower() == "c" or argv[1].lower() == "client":
    proxy = AsyncMitmProxy(RequestHandlerClass=ClientMitmProxyHandler)

  # launch server
  elif argv[1].lower() == "s" or argv[1].lower() == "server":
    proxy = AsyncMitmProxy(RequestHandlerClass=ServerMitmProxyHandler)

  # launch 'test'
  elif argv[1].lower() == "t" or argv[1].lower() == "test":
    proxy = AsyncMitmProxy(RequestHandlerClass=TestMitmProxyHandler)

  # launch... none
  else:
    print "Bad argument. Expect [c/s/t]"

  # add interceptor and run
  #proxy.register_interceptor(DebugInterceptor)
  try:
    proxy.serve_forever()
  except KeyboardInterrupt:
    proxy.server_close()

  
if __name__ == "__main__":
  _main()
