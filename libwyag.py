
#! step1: import necessary module
import argparse                     # parse command-line arguments
import collections                  # more container types(like OrderDict)
import configparser                 # parse .ini format configuration file(maybe store config user.name etc.)
from datetime import datetime       # for some date/time manipulation
# import grp, pwd                     # to read the users/group database on Unix( git saves the numerical owner/group ID of files, and we’ll want to display that nicely)
import fnmatch                      # for .gitignore file, not re but file name match
import hashlib                      # git uses SHA-1 function(extensively)
from math import ceil               # just a ceil function(round up function)
import os                           # os and os.path to process filesystem
import re                           # still need a bit of regular expressions
import sys                          # access the command-line arguments(sys.argv)
import zlib                         # git compresses everything using zlib



#! step2: parse arg
# main object to process command-line arguments
argparser = argparse.ArgumentParser(description="The stupidest content tracker")

# deal with subcommands(like: git config options)
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")  # dest means the commands will be in a field called command
argsubparsers.required = True   # when use, must need subcommand(init, config, commit, etc. the actual command)

# link subcommands to bridge function
def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)  # parse and get the command-line arguments
    # use match to deal with subcommands(which are must required)
    match args.command:  # in line 23, subparsers' commands are in filed command
        # use bridge function to exactly process the subcommand(prefix cmd_)
        case "add"          : cmd_add(args)
        case "cat-file"     : cmd_cat_file(args)
        case "check-ignore" : cmd_check_ignore(args)
        case "checkout"     : cmd_checkout(args)
        case "commit"       : cmd_commit(args)
        case "hash-object"  : cmd_hash_object(args)
        case "init"         : cmd_init(args)
        case "log"          : cmd_log(args)
        case "ls-files"     : cmd_ls_files(args)
        case "ls-tree"      : cmd_ls_tree(args)
        case "merge"        : cmd_merge(args)
        case "rebase"       : cmd_rebase(args)
        case "rev-parse"    : cmd_rev_parse(args)
        case "rm"           : cmd_rm(args)
        case "show-ref"     : cmd_show_ref(args)
        case "status"       : cmd_status(args)
        case "tag"          : cmd_tag(args)
        case _              : print("Bad command.")  # default (can be replaced by help)


#! step3: create repositories: init
class GitRepository(object):
    """
    A git repository.
    abstraction for a repository, like a file object,
    we create it, read from it and modify it.
    """
    worktree = None # user's work directory
    gitdir = None   # .git directory
    conf = None     # configuration (.git/config, just a INI file)

    def __init__(self, path, force=False):
        """
        path : the work directory
        force : to create repository even from (still) invalid filesystem locations
        """
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            # if force == True, skip gitdir check and pass
            # if force == False, check the gitdir is a directory
            raise Exception(f"Not a Git repository {path}")
        
        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")  # to get config file path

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")
        
        # about version control, make sure core.repositoryformatversion is 0
        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")


#? some utility functions to compute paths(base repo) and create them if needed
def repo_path(repo, *path):
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
    """Same as repo_path but create dirname(*path) if absent."""
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)
    
def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path but mkdir *path if absent if mkdir"""
    path = repo_path(repo, *path)
    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f"Not a directory {path}")
        
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None
    

""" sub directories in .git/
.git/objects/   : the object store
.git/refs/      : the reference store(contains 2 subdirectories heads and tags)
.git/description: holds a free-form description of this repository’s contents, for humans, and is rarely used.
"""

def repo_create(path):
    """Create a new repository at path."""

    repo = GitRepository(path, force=True)

    # make sure path not exist and not empty
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)
    
    # .git maybe exists but necessary sub dir not exists
    assert repo_dir(repo, "branch", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)    # .git/refs/tags
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # .git/description
    with open(repo_file(repo, "description"), 'w') as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), 'w') as f:
        f.write("ref: refs/heads/master\n")
    
    # .git/config (INI-like file)
    """
    a single section:
        core
    three fields:
        repositoryformatversion = 0
            the version of the gitdir format.
            0: the initial format
            1: the same with extensions
            >1: git will panic
            ! wyag will only accept 0
        filemode = false
            disable tracking file mode(permissions) changes
        bare = false
            indicates this repository has a worktree.
            Git supports an optional worktree key which indicates the location of the worktree, fi not ..
            ! wyag doesn't
    """
    with open(repo_file(repo, "config"), 'w') as f:
        config = repo_default_config()
        config.write(f)
    
    return repo

def repo_default_config():
    config = configparser.ConfigParser()

    config.add_section("core")
    config.set("core", "repositoryformatversion", "0")
    config.set("core", "filemode", "false")
    config.set("core", "bare", "false")
    
    return config


# ?deal with init command

argsp = argsubparsers.add_parser("init", help="Initialize a new, empty repository.")

argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository. default by cwd.")

def cmd_init(args):
    repo_create(args.path)


# repo_find() function to find the .git in parent directory
def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)
    
    # if not return, recurse in parent
    parent = os.path.realpath(os.path.join(path, ".."))

    if parent == path:  # os.path.join("/", "..") == "/"
        if required:  # must need a .git
            raise Exception("No git directory.")
        else:
            return None
    return repo_find(parent, required)


#! step4: reading and writing objects: hash-object and cat-file
# hash-object: converts an existing file into a git object
# cat-file: prints an existing git object to standard output
'''
 Objects are just that: files in the git repository, 
 whose paths are determined by their contents.
 Git is not (really) a key-value store
 Because it computes keys from data, 
 Git should rather be called a value-value store.

 Git uses objects to store quite a lot of things:
 - the actual files it keeps in version control(source code, etc.)
 - Commit are objects, too, 
 - as well as tags. 
 with a few notable exceptions
 almost everything, in Git, is stored as an object.

 Git renders the hash(SHA-1 hash) as a lowercase hexadecimal string, 
 and splits it in two parts:
 - the first two characters:
        use it as a directory name
- the rest
        use it as the file name

An object starts with a header that specifies its type: 
blob, commit, tag or tree (more on that in a second). 
This header is followed by an ASCII space (0x20), 
then the size of the object in bytes as an ASCII number, 
then null (0x00) (the null byte), then the contents of the object. 
'''

# A generic Git Object, with 2 unimplemented methods
class GitObject(object):
    def __init__(self, data=None):
        if data is not None:
            self.deserialize(data)
        else:
            self.init()
    
    def serialize(self, repo):
        """
        This function MUST be implemented by subclasses.
        It must read the object's contents from self.data,
        a byte string, and do whatever it takes to convert
        it into a meaningful representation.
        It depend on each subclass
        """
        raise NotImplementedError
    
    def deserialize(self, data):
        raise NotImplementedError
    
    def init(self):
        pass  # Do noting. This is a reasonable default!


# reading objects
'''
To read an object, we need to know its hash.
We then compute its path from this hash 
(with the formula explained above: first two characters, 
then a directory delimiter /, then the remaining part)
and look it up inside of the “objects” directory in the gitdir. 
 That is, the path to e673d1b7eaa0aa01b5bc2442d570a765bdaae751 is
   .git/objects/e6/73d1b7eaa0aa01b5bc2442d570a765bdaae751.
'''
def object_read(repo, sha):
    """
    Read object sha from Git repository repo.
    Return a GitObject whose exact type depends
    on the object.
    """
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None
    
    with open(path, 'rb') as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode('ascii'))
        if size != len(raw)-y-1:
            raise Exception(f"Malformed object {sha}: bad length")
        
        # Pick constructor
        match fmt:
            case b'commit'  : c = GitCommit
            case b'tree'    : c = GitTree
            case b'tag'     : c = GitTag
            case b'blob'    : c = GitBlob
            case _:
                raise Exception(f"Unknown type {fmt.decode('ascii')} \
                                for object {sha}")
        # Call constructor and return object
        return c(raw[y+1:])

def object_find(repo, name, fmt=None, follow=True):
    # support short hash (not implement)
    return name

# Writing objects
# notice that the hash is computed after the header is added.
def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # ! Add header (notice )
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # Compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, 'wb') as f:
                # Compress and write
                f.write(zlib.compress(result))
    return sha

# type header could be one of four: blob, commit, tag and tree
#  — so git has four object types.

# working with blobs
'''
blobs are the simplest, because they have no actual format.
Blobs are user data: the content of every file you put in git 
(main.c, logo.png, README.md) is stored as a blob. 
they have no actual syntax or constraints beyond the basic 
object storage mechanism: they're just unspecified data.
'''
class GitBlob(GitObject):
    fmt = b'blob'

    def serialize(self):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata = data

# git cat-file TYPE OBJECT: 
# prints the raw contents of an object to stdout, 
# just uncompressed and header removed. 

argsp = argsubparsers.add_parser("cat-file",
                                 help="Provide content of repository objects")
argsp.add_argument("type",
                   metavar="type",
                   choices=["blob", "commit", "tag", "tree"],
                   help="Specify the type")
argsp.add_argument("object",
                   metavar="object",
                   help="The object to display")

def cmd_cat_file(args):
    repo = repo_find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())


# the hash-object command
# git hash-object [-w] [-t Type] FILE
"""
the opposite of cat-file:
it reads a file, computes its hash as an object,
either storing it in the repository(passed -w)
or just printing its hash
"""
argsp = argsubparsers.add_parser(
    "hash-object",
    help="Compute object ID and optionally creates a blob from a file"
)
argsp.add_argument("-t",
                   metavar="type",
                   dest="type",
                   choices=["blob", "commit","tag", "tree"],
                   default="blob",
                   help="Specify the type")
argsp.add_argument("-w",
                   dest="write",
                   action="store_true",
                   help="Actually write the object into the database")
argsp.add_argument("path",
                   help="Read object from <file>")

def cmd_hash_object(args):
    if args.write:
        repo = repo_file()
    else:
        repo = None
    with open(args.path, 'rb') as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

def object_hash(fd, fmt, repo=None):
    '''hash object, writing it to repo if provided'''
    data = fd.read()

    # choose constructor according to fmt argument
    match fmt:
        case b"commit"  : obj = GitCommit(data)
        case b"tree"    : obj = GitTree(data)
        case b"tag"     : obj = GitTag(data)
        case b'blob'    : obj = GitBlob(data)
        case _          : raise Exception(f"Unknown type {fmt}")
    return object_write(obj, repo)


''' notice
What we've just implemented is called “loose objects”. 
Git has a second object storage mechanism called packfiles. 
Packfiles are much more efficient, but also much more complex, 
than loose objects. Simply put, a packfile is a compilation 
of loose objects (like a tar) but some are stored as deltas 
(as a transformation of another object). Packfiles are way 
too complex to be supported by wyag.

The packfile is stored in .git/objects/pack/. It has a .pack 
extension, and is accompanied by an index file of the same 
name with the .idx extension. 
'''

# ! step5: reading commit history:log
def kvlm_parse(raw, start=0, dct=None): # Key-Value List with Message
    if dct is not None:
        dct = collections.OrderedDict()
    '''
    This function is recursive: it reads a key/value pair, then call
    itself back with the new position.  So we first need to know
    where we are: at a keyword, or already in the messageQ
    '''
    # search for the next space and the next newline
    spc = raw.find(b' ', start)
    nl = raw.find(b'\n', start)

    # base case
    if (spc<0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start+1:]
        return dct
    
    # recursive case
    key = raw[start:spc]
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): break
    
    # Grab the value
    value = raw[spc+1:end].replace(b'\n ', b'\n')

    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [ dct[key], value ]
    else:
        dct[key] = value
    
    return kvlm_parse(raw, start=end+1, dct=dct)


def kvlm_serialize(kvlm):
    ret = b''

    #output fields
    for k in kvlm.keys():
        # Skip the message itself
        if k is None: continue
        val = kvlm[k]
        # normalize to a list
        if type(val) != list:
            val = [val]

        for v in val:
            ret += k + b' ' +  (v.replace(b'\n', b'\n ')) + b'\n'
    
    # append message
    ret += b'\n' + kvlm[None] + b'\n'

    return ret


class GitCommit(GitObject):
    fmt = b'commit'

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)
    
    def serialize(self):
        return kvlm_serialize(self.kvlm)

    def init(self):
        self.kvlm = dict()


# the log command
argsp = argsubparsers.add_parser("log",
                                 help="Display history of a given commit.")
argsp.add_argument("commit",
                   default="HEAD",
                   nargs="?",
                   help="Commit to start at.")

def cmd_log(args):
    repo = repo_find()
    print("digraph wyaglog{}")
    print("  node[shape=rect]")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print("}")

def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    short_hash = sha[0:8]
    message = commit.kvlm[None].decode("utf-8").strip()
    message = message.replace("\\", "\\\\")
    message = message.replace("\"", "\\\"")

    if "\n" in message:  # keep only the first line
        message = message[:message.index("\n")]

    print(f"  c_{sha} [label=\"{sha[0:7]}: {message}\"]")
    assert commit.fmt == b'commit'

    if not b'parent' in commit.kvlm.keys():
        return
    
    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [parents]
    
    for p in parents:
        p = p.decode("ascii")
        print("  c_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)


#! step6: reading commit data: checkout
