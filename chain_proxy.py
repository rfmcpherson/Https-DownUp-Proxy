# Extension to PyMiProxy
# by Richard McPherson
# heavily based on and includes code by Nadeem Douba 
# GPL

from httplib import HTTPResponse, BadStatusLine
from ssl import wrap_socket
from socket import socket, SHUT_RDWR
from urlparse import urlparse, urlunparse, ParseResult

from proxy import *

# class that allows chained proxies
class ChainedMitmProxyHandler(ProxyHandler):
  protocol_version = "HTTP/1.1"

  # proxy_address: 
  #  ([str]address, [int]port) of next proxy
  #  None if last proxy
  # ssl_next:
  #  boolean to determine if next hop is forced to be HTTP
  # ssl_prev:
  #  boolean to determine if prev hop is forced to be HTTP
  def __init__(self, request, client_address, server, proxy_address=None, ssl_next=True, ssl_prev=True):
    if proxy_address:
      self.proxy_address = proxy_address
    self.ssl_next = ssl_next
    self.ssl_prev = ssl_prev
    ProxyHandler.__init__(self, request, client_address, server)


  # connect to next proxy or endpoint
  def _connect_to_host(self):
    if not self.is_connect:
      self._get_address()

    # Connect to destination
    self._proxy_sock = socket()
    self._proxy_sock.settimeout(10)

    # connect to next proxy or endpoint
    if self.proxy_address:
      self._proxy_sock.connect(self.proxy_address)
    else:
      self._proxy_sock.connect((self.hostname, self.port))

    # wrap socket in ssl if needed
    if self.is_connect and self.ssl_next:
        self._proxy_sock = wrap_socket(self._proxy_sock, server_side=False)

    # send CONNECT request if chained
    if self.is_connect and self.proxy_address:
      req = self._get_request(connect=True)
      self._proxy_sock.sendall(self.mitm_request(req))


  # get hostname and port
  # reset self.path as needed
  def _get_address(self):
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
    self.port = int(self.port)


  # return request
  def _get_request(self, connect=False):
    if connect:
      req = "{} {}:{} {}\r\n".format(self.command, self.hostname, self.port, self.request_version)
    else:
      req = "{} {} {}\r\n".format(self.command, self.path, self.request_version)


    # Add headers to the request
    req += "{}\r\n".format(self.headers)
        
    # Append message body if present to the request
    if 'Content-Length' in self.headers:
      req += self.rfile.read(int(self.headers['Content-Length']))
      
    return req

  def do_CLOSE(self):
    print "IT WORKED!"

  def do_COMMAND(self):
    print self.protocol_version

    close = False

    # Is this an SSL tunnel?
    if not self.is_connect:
      try:
        # Connect to destination
        self._connect_to_host()
      except Exception, e:
        self.send_error(500, str(e))
        return
      # Extract path

    # Build request
    req = self._get_request(connect=False)
    
    # Check if last request
    #if "Connection" in self.headers and self.headers['Connection'] == "close":
    #  close = True
    #  print "client close"
    self.headers['Connection'] = "close"

    # Send it down the pipe!
    self._proxy_sock.sendall(self.mitm_request(req))


    # Parse response
    try:
      h = HTTPResponse(self._proxy_sock)
      h.begin()
    except BadStatusLine:
      print "BadStatusLine, closing"
      self.request.shutdown(SHUT_RDWR)
      self.request.close()
      h.close()
      return

    # Check if last response
    #if "Connection" in h.msg and h.msg['Connection'] == "close":
    #  close = True
    #  print "server close"
    h.msg['Connection'] = "close"

    # Get rid of the pesky header
    del h.msg['Transfer-Encoding']
    
    # Time to relay the message across
    res = '%s %s %s\r\n' % (self.request_version, h.status, h.reason)
    res += '%s\r\n' % h.msg
    res += h.read()

    # Relay the message
    self.request.sendall(self.mitm_response(res))

    # Let's close off the remote end
    #if close:
    print "closing"
    h.close()
    self.request.shutdown(SHUT_RDWR)
    self.request.close()
    print "closed"

    #if not close:
    #  self.handle_one_request()

  def do_CONNECT(self):
    self.is_connect = True
    try:
      # Connect to destination first
      self._get_address()
      self._connect_to_host()

      # If successful, let's do this!
      if self.ssl_prev:
        self.send_response(200, 'Connection established')
        self.end_headers()
        self._transition_to_ssl()
    except Exception, e:
      self.send_error(500, str(e))
      return

    # Reload!
    self.setup()
    self.ssl_host = 'https://%s' % self.path
    self.handle_one_request()



# HTTPS to HTTP
class ClientMitmProxyHandler(ChainedMitmProxyHandler):

  def __init__(self, request, client_address, server):
    # TODO: fix
    ChainedMitmProxyHandler.__init__(self, request, client_address, server, ('localhost',8081), False, True)



# HTTP to HTTPS
class ServerMitmProxyHandler(ChainedMitmProxyHandler):

  def __init__(self, request, client_address, server):
    ChainedMitmProxyHandler.__init__(self, request, client_address, server, None, True, False)



# Make sure this code is working
class TestMitmProxyHandler(ChainedMitmProxyHandler):

  def __init__(self, request, client_address, server):
    ChainedMitmProxyHandler.__init__(self, request, client_address, server, None, True, True)



# Prints first line of Reqeust and Response
class FirstLineInterceptor(RequestInterceptorPlugin, ResponseInterceptorPlugin):
  def do_request(self, data):
    line = data.split("\r\n")[0]
    print '>> %s' % repr(line)
    return data
  def do_response(self, data):
    line = data.split("\r\n")[0]
    print '<< %s' % repr(line)
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
    proxy = AsyncMitmProxy(
      RequestHandlerClass=ClientMitmProxyHandler, 
      server_address=('localhost',8080))
    
  # launch server
  elif argv[1].lower() == "s" or argv[1].lower() == "server":
    proxy = AsyncMitmProxy(
      RequestHandlerClass=ServerMitmProxyHandler, 
      server_address=('localhost',8081))

  # launch 'test'
  elif argv[1].lower() == "t" or argv[1].lower() == "test":
    proxy = AsyncMitmProxy(
      RequestHandlerClass=TestMitmProxyHandler, 
      server_address=('localhost',8080))

  # launch... none
  else:
    print "Bad argument. Expect [c/s/t]"

  # add interceptor and run
  proxy.register_interceptor(FirstLineInterceptor)

  #proxy.run_proxy()

  
  try:
    proxy.serve_forever()
  except KeyboardInterrupt:
    proxy.shutdown()
  

if __name__ == "__main__":
  _main()
