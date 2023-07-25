# from libwyag import *
import os
#
# repo = GitRepository(os.getcwd())
#
# print(repo_path(repo, ))


# def get(repo, *path):
#     return os.path.join()
print(os.path.join("C:/Users", *('ab/c', 'ab/d.txt')))
print([*[1,2,3]])
print(*(1,2,3))


import urllib3 as lib

http = lib.PoolManager()
res = http.request(method='GET', url='https://www.baidu.com')
print(res.data.decode('utf-8'))
