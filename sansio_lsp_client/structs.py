import collections

Request = collections.namedtuple("Request", "method params")
Response = collections.namedtuple("Response", "headers id result error")
