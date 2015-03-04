# Extension to PyMiProxy
# by Richard McPherson
# based on code by Nadeem Douba 
# GPL

from ssl import wrap_socket
from socket import socket

from proxy import *

# HTTPS to HTTP
class ClientMitmProxyHandler(ProxyHandler):

  def __init__(self, request, client_address, server):
    self.chain_hostname = "localhost"
    self.chain_port = 8081
    ProxyHandler.__init__(self, request, client_address, server)
  
  # builds up the initial request
  def _build_connect(self):
    # Build request
    #req = '%s %s %s\r\n' % (self.command, self.path, self.request_version)
    req = "{} {}:{} {}\r\n".format(self.command, self.hostname, self.port, self.request_version)

    # Add headers to the request
    req += '%s\r\n' % self.headers
        
    # Append message body if present to the request
    if 'Content-Length' in self.headers:
      req += self.rfile.read(int(self.headers['Content-Length']))
      
    return req


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

    # proxy chain
    if(1):
      self._proxy_sock.connect((self.chain_hostname, int(self.chain_port)))
    # no proxy chain
    else:
      self._proxy_sock.connect((self.hostname, int(self.port)))
      
    # wrap outbound socket
    if(0):
      if self.is_connect:
        self._proxy_sock = wrap_socket(self._proxy_sock)

    # send HTTP CONNECT
    if self.is_connect:
      req = self._build_connect()
      self._proxy_sock.sendall(self.mitm_request(req))


# HTTP to HTTPS
class ServerMitmProxyHandler(ProxyHandler):

  # Overwrite _transition_to_ssl
  # Changes:
  #    Not wrapping socket with ssl
  def _transition_to_ssl(self):
        pass

  # Overwrite do_CONNECT
  # Changes:
  #    Remove that 200 response
  def do_CONNECT(self):
    self.is_connect = True
    try:
      # Connect to destination first
      self._connect_to_host()
      
      # If successful, let's do this!
      #self.send_response(200, 'Connection established')
      #self.end_headers()
      #self.request.sendall('%s 200 Connection established\r\n\r\n' % self.request_version)
      self._transition_to_ssl()
    except Exception, e:
      self.send_error(500, str(e))
      return

    # Reload!
    self.setup()
    self.ssl_host = 'https://%s' % self.path
    self.handle_one_request()


# Make sure this code is working
class TestMitmProxyHandler(ProxyHandler):
  pass


# From PyMiProxy
class DebugInterceptor(RequestInterceptorPlugin, ResponseInterceptorPlugin):
  def do_request(self, data):
    print '>> %s' % repr(data[:100])
    return data
  def do_response(self, data):
    print '<< %s' % repr(data[:100])
    return data



class SaveDebugInterceptor(RequestInterceptorPlugin, ResponseInterceptorPlugin):
  def do_request(self, data):
    return data
  def do_response(self, data):
    with open("res","wb") as f:
      f.write(data)
    return data


def _main():
  from sys import argv
  proxy = None

  # check for argument
  if not argv[1]:
    print "Need one argument: [c/s/t]"
    return

  # launch client
  if argv[1].lower() == "c" or argv[1].lower() == "client":
    proxy = AsyncMitmProxy(RequestHandlerClass=ClientMitmProxyHandler, server_address=('localhost',8080))
    proxy.register_interceptor(SaveDebugInterceptor)

  # launch server
  elif argv[1].lower() == "s" or argv[1].lower() == "server":
    proxy = AsyncMitmProxy(RequestHandlerClass=ServerMitmProxyHandler, server_address=('localhost',8081))

  # launch 'test'
  elif argv[1].lower() == "t" or argv[1].lower() == "test":
    proxy = AsyncMitmProxy(RequestHandlerClass=TestMitmProxyHandler, server_address=('localhost',8081))

  # launch... none
  else:
    print "Bad argument. Expect [c/s/t]"

  # add interceptor and run
  proxy.register_interceptor(DebugInterceptor)
  try:
    proxy.serve_forever()
  except KeyboardInterrupt:
    proxy.server_close()



if __name__ == "__main__":
  _main()
