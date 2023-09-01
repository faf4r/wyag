#! step1: import necessary module
import argparse  # parse command-line arguments
import collections  # more container types(like OrderDict)
import configparser  # parse .ini format configuration file(maybe store config user.name etc.)
from datetime import datetime  # for some date/time manipulation
import grp, pwd  # to read the users/group database on Unix( git saves the numerical owner/group ID of files, and we’ll want to display that nicely)
import fnmatch  # for .gitignore file, not re but file name match
import hashlib  # git uses SHA-1 function(extensively)
from math import ceil  # just a ceil function(round up function)
import os  # os and os.path to process filesystem
import re  # still need a bit of regular expressions
import sys  # access the command-line arguments(sys.argv)
import zlib  # git compresses everything using zlib


#! step2: parse arg
# main object to process command-line arguments
argparser = argparse.ArgumentParser(description="The stupidest content tracker")

# deal with subcommands(like: git config options)
argsubparsers = argparser.add_subparsers(
    title="Commands", dest="command"
)  # dest means the commands will be in a field called command
argsubparsers.required = True  # when use, must need subcommand(init, config, commit, etc. the actual command)


# link subcommands to bridge function
def main(argv=sys.argv[1:]):
    args = argparser.parse_args(argv)  # parse and get the command-line arguments
    # use match to deal with subcommands(which are must required)
    match args.command:  # in line 23, subparsers' commands are in filed command
        # use bridge function to exactly process the subcommand(prefix cmd_)
        case "add":
            cmd_add(args)
        case "cat-file":
            cmd_cat_file(args)
        case "check-ignore":
            cmd_check_ignore(args)
        case "checkout":
            cmd_checkout(args)
        case "commit":
            cmd_commit(args)
        case "hash-object":
            cmd_hash_object(args)
        case "init":
            cmd_init(args)
        case "log":
            cmd_log(args)
        case "ls-files":
            cmd_ls_files(args)
        case "ls-tree":
            cmd_ls_tree(args)
        case "merge":
            cmd_merge(args)
        case "rebase":
            cmd_rebase(args)
        case "rev-parse":
            cmd_rev_parse(args)
        case "rm":
            cmd_rm(args)
        case "show-ref":
            cmd_show_ref(args)
        case "status":
            cmd_status(args)
        case "tag":
            cmd_tag(args)
        case _:
            print("Bad command.")  # default (can be replaced by help)


#! step3: create repositories: init
class GitRepository(object):
    """
    A git repository.
    abstraction for a repository, like a file object,
    we create it, read from it and modify it.
    """

    worktree = None  # user's work directory
    gitdir = None  # .git directory
    conf = None  # configuration (.git/config, just a INI file)

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


# ? some utility functions to compute paths(base repo) and create them if needed
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
    assert repo_dir(repo, "refs", "tags", mkdir=True)  # .git/refs/tags
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write(
            "Unnamed repository; edit this file 'description' to name the repository.\n"
        )

    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
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
    with open(repo_file(repo, "config"), "w") as f:
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

argsp.add_argument(
    "path",
    metavar="directory",
    nargs="?",
    default=".",
    help="Where to create the repository. default by cwd.",
)


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
"""
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
"""


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
"""
To read an object, we need to know its hash.
We then compute its path from this hash 
(with the formula explained above: first two characters, 
then a directory delimiter /, then the remaining part)
and look it up inside of the “objects” directory in the gitdir. 
 That is, the path to e673d1b7eaa0aa01b5bc2442d570a765bdaae751 is
   .git/objects/e6/73d1b7eaa0aa01b5bc2442d570a765bdaae751.
"""


def object_read(repo, sha):
    """
    Read object sha from Git repository repo.
    Return a GitObject whose exact type depends
    on the object.
    """
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # Read object type
        x = raw.find(b" ")
        fmt = raw[0:x]

        # Read and validate object size
        y = raw.find(b"\x00", x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw) - y - 1:
            raise Exception(f"Malformed object {sha}: bad length")

        # Pick constructor
        match fmt:
            case b"commit":
                c = GitCommit
            case b"tree":
                c = GitTree
            case b"tag":
                c = GitTag
            case b"blob":
                c = GitBlob
            case _:
                raise Exception(
                    f"Unknown type {fmt.decode('ascii')} \
                                for object {sha}"
                )
        # Call constructor and return object
        return c(raw[y + 1 :])


def object_find(repo, name, fmt=None, follow=True):
    # support short hash (not implement)
    return name


# Writing objects
# notice that the hash is computed after the header is added.
def object_write(obj, repo=None):
    # Serialize object data
    data = obj.serialize()
    # ! Add header (notice )
    result = obj.fmt + b" " + str(len(data)).encode() + b"\x00" + data
    # Compute hash
    sha = hashlib.sha1(result).hexdigest()

    if repo:
        # Compute path
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            with open(path, "wb") as f:
                # Compress and write
                f.write(zlib.compress(result))
    return sha


# type header could be one of four: blob, commit, tag and tree
#  — so git has four object types.

# working with blobs
"""
blobs are the simplest, because they have no actual format.
Blobs are user data: the content of every file you put in git 
(main.c, logo.png, README.md) is stored as a blob. 
they have no actual syntax or constraints beyond the basic 
object storage mechanism: they're just unspecified data.
"""


class GitBlob(GitObject):
    fmt = b"blob"

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data


# git cat-file TYPE OBJECT:
# prints the raw contents of an object to stdout,
# just uncompressed and header removed.

argsp = argsubparsers.add_parser(
    "cat-file", help="Provide content of repository objects"
)
argsp.add_argument(
    "type",
    metavar="type",
    choices=["blob", "commit", "tag", "tree"],
    help="Specify the type",
)
argsp.add_argument("object", metavar="object", help="The object to display")


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
    "hash-object", help="Compute object ID and optionally creates a blob from a file"
)
argsp.add_argument(
    "-t",
    metavar="type",
    dest="type",
    choices=["blob", "commit", "tag", "tree"],
    default="blob",
    help="Specify the type",
)
argsp.add_argument(
    "-w",
    dest="write",
    action="store_true",
    help="Actually write the object into the database",
)
argsp.add_argument("path", help="Read object from <file>")


def cmd_hash_object(args):
    if args.write:
        repo = repo_file()
    else:
        repo = None
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)


def object_hash(fd, fmt, repo=None):
    """hash object, writing it to repo if provided"""
    data = fd.read()

    # choose constructor according to fmt argument
    match fmt:
        case b"commit":
            obj = GitCommit(data)
        case b"tree":
            obj = GitTree(data)
        case b"tag":
            obj = GitTag(data)
        case b"blob":
            obj = GitBlob(data)
        case _:
            raise Exception(f"Unknown type {fmt}")
    return object_write(obj, repo)


""" notice
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
"""


# ! step5: reading commit history:log
def kvlm_parse(raw, start=0, dct=None):  # Key-Value List with Message
    if dct is not None:
        dct = collections.OrderedDict()
    """
    This function is recursive: it reads a key/value pair, then call
    itself back with the new position.  So we first need to know
    where we are: at a keyword, or already in the messageQ
    """
    # search for the next space and the next newline
    spc = raw.find(b" ", start)
    nl = raw.find(b"\n", start)

    # base case
    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start + 1 :]
        return dct

    # recursive case
    key = raw[start:spc]
    end = start
    while True:
        end = raw.find(b"\n", end + 1)
        if raw[end + 1] != ord(" "):
            break

    # Grab the value
    value = raw[spc + 1 : end].replace(b"\n ", b"\n")

    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [dct[key], value]
    else:
        dct[key] = value

    return kvlm_parse(raw, start=end + 1, dct=dct)


def kvlm_serialize(kvlm):
    ret = b""

    # output fields
    for k in kvlm.keys():
        # Skip the message itself
        if k is None:
            continue
        val = kvlm[k]
        # normalize to a list
        if type(val) != list:
            val = [val]

        for v in val:
            ret += k + b" " + (v.replace(b"\n", b"\n ")) + b"\n"

    # append message
    ret += b"\n" + kvlm[None] + b"\n"

    return ret


class GitCommit(GitObject):
    fmt = b"commit"

    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)

    def serialize(self):
        return kvlm_serialize(self.kvlm)

    def init(self):
        self.kvlm = dict()


# the log command
argsp = argsubparsers.add_parser("log", help="Display history of a given commit.")
argsp.add_argument("commit", default="HEAD", nargs="?", help="Commit to start at.")


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
    message = message.replace('"', '\\"')

    if "\n" in message:  # keep only the first line
        message = message[: message.index("\n")]

    print(f'  c_{sha} [label="{sha[0:7]}: {message}"]')
    assert commit.fmt == b"commit"

    if not b"parent" in commit.kvlm.keys():
        return

    parents = commit.kvlm[b"parent"]

    if type(parents) != list:
        parents = [parents]

    for p in parents:
        p = p.decode("ascii")
        print("  c_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)


#! step6: reading commit data: checkout
"""
tree's format:
[mode] space [path] 0x00 [sha-1]
[mode] is up to six bytes and is an octal representation of a file mode, stored in ASCII. For example, 100644 is encoded with byte values 49 (ASCII “1”), 48 (ASCII “0”), 48, 54, 52, 52. The first two digits encode the file type (file, directory, symlink or submodule), the last four the permissions.
It's followed by 0x20, an ASCII space;
Followed by the null-terminated (0x00) path;
Followed by the object's SHA-1 in binary encoding, on 20 bytes.
"""


class GitTreeLeaf(object):
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha


def tree_parse_one(raw, start=0):
    # find the space terminator of the mode
    x = raw.find(b" ", start)
    assert x - start == 5 or x - start == 6

    # read the mode
    mode = raw[start:x]
    if len(mode) == 5:
        # normalize to six bytes
        mode = b" " + mode

    # find the NULL terminator of the path
    y = raw.find(b"\x00", x)
    path = raw[x + 1 : y]

    # read the SHA and convert to a hex string
    sha = format(int.from_bytes(raw[y + 1 : y + 21], "big"), "040x")
    return y + 21, GitTreeLeaf(mode, path.decode("utf-8"), sha)


def tree_parse(raw):
    pos = 0
    max = len(raw)
    ret = list()
    while pos < max:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)
    return ret


def tree_leaf_sort_key(leaf):
    if leaf.mode.startswith(b"10"):
        return leaf.path
    else:
        return leaf.path + "/"


def tree_serialize(obj):
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b""
    for i in obj.items:
        ret += i.mode
        ret += b" "
        ret += i.path.encode("utf-8")
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")
    return ret


class GitTree(GitObject):
    fmt = b"tree"

    def deserialize(self, data):
        self.items = tree_parse(data)

    def serialize(self):
        return tree_serialize(self)

    def init(self):
        self.items = list()


# showing trees: ls-tree
"""
git ls-tree [-r] TREE simply prints the contents of a tree, 
recursively with the -r flag. In recursive mode, 
it doesn't show subtrees, just final objects with their full paths.
"""

argsp = argsubparsers.add_parser("ls-tree", help="Pretty-print a tree object")
argsp.add_argument(
    "-r", dest="recursive", action="store_true", help="Recurse into sub-trees"
)
argsp.add_argument("tree", help="A tree-ish object.")


def cmd_ls_tree(args):
    repo = repo_find()
    ls_tree(repo, args.tree, args.recursive)


def ls_tree(repo, ref, recursive=None, prefix=""):
    sha = object_find(repo, ref, fmt=b"tree")
    obj = object_read(repo, sha)
    for item in obj.items:
        if len(item.mode) == 5:
            type = item.mode[0:1]
        else:
            type = item.mode[0:2]

        match type:
            case b"04":
                type = "tree"
            case b"10":
                type = "blob"
            case b"12":
                type = "blob"
            case b"16":
                type = "commit"
            case _:
                raise Exception(
                    f"\
                     weird tree leaf mode {item.mode}"
                )
        if not (recursive and type == "tree"):  # This is a leaf
            print(
                f"{'0'*(6-len(item.mode)) + item.mode.decode('ascii')} \
                   {type} {item.sha}\t{os.path.join(prefix, item.path)}"
            )
        else:
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))


# checkout command
argsp = argsubparsers.add_parser(
    "checkout",
    help="Checkout a commit inside of \
                                    of a directory.",
)
argsp.add_argument("commit", help="The commit or tree to checkout.")
argsp.add_argument("path", help="The EMPTY directory to checkout on.")


def cmd_checkout(args):
    repo = repo_file()
    obj = object_read(repo, object_find(repo, args.commit))

    if obj.fmt == b"commit":
        obj = object_read(repo, obj.kvlm[b"tree"].decode("ascii"))

    if os.path.exists(args.path):
        if not os.path.isdir(args.path):
            raise Exception(f"Not a directory {args.path}!")
        if os.listdir(args.path):
            raise Exception(f"Not empty {args.path}!")
    else:
        os.makedirs(args.path)

    tree_checkout(repo, obj, os.path.realpath(args.path))


def tree_checkout(repo, tree, path):
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(path, item.path)

        if obj.fmt == b"tree":
            os.mkdir(dest)
            tree_checkout(repo, obj, dest)
        elif obj.fmt == b"blob":
            with open(dest, "wb") as f:
                f.write(obj.blobdata)


#! step7: Refs, tags and branches
"""call a reference of the form ref: path/to/other/ref an 
indirect reference, and a ref with a SHA-1 object ID 
a direct reference."""


def ref_resolve(repo, ref):
    path = repo_file(repo, ref)

    if not os.path.isfile(path):
        return None

    with open(path, "r") as fp:
        data = fp.read()[:-1]  # drop '\n'

    if data.startswith("ref: "):
        return ref_resolve(repo, data[5:])
    else:
        return data


def ref_list(repo, path=None):
    if path is None:
        path = repo_dir(repo, "refs")
    ret = collections.OrderedDict()

    for f in sorted(os.listdir(path)):
        can = os.path.join(path, f)
        if os.path.isdir(can):
            ret[f] = ref_list(repo, can)
        else:
            ret[f] = ref_resolve(repo, can)
    return ret


argsp = argsubparsers.add_parser("show-ref", help="List references.")


def cmd_show_ref(args):
    repo = repo_find()
    refs = ref_list(repo)
    show_ref(repo, refs, prefix="refs")


def show_ref(repo, refs, with_hash=True, prefix=""):
    for k, v in refs.items():
        if type(v) == str:
            print(
                f"{v+' ' if with_hash else ''}\
                  {prefix+'/' if prefix else ''}{k}"
            )
        else:
            show_ref(
                repo,
                v,
                with_hash=with_hash,
                prefix="{0}{1}{2}".format(prefix, "/" if prefix else "", k),
            )


# tags as references
"""
git tag v12.78.52 6071c08
# the object hash ^here^^ is optional and defaults to HEAD.

“Lightweight” tags:
    are just regular refs to a commit, a tree or a blob.
Tag objects:
    are regular refs pointing to an object of type tag. 
    Unlike lightweight tags, tag objects have an author, 
    a date, an optional PGP signature and an optional 
    annotation. Their format is the same as a commit object.
"""


class GitTag(GitCommit):
    fmt = b"tag"


"""
git tag                  # List all tags
git tag NAME [OBJECT]    # create a new *lightweight* tag NAME, pointing
                         # at HEAD (default) or OBJECT
git tag -a NAME [OBJECT] # create a new tag *object* NAME, pointing at
                         # HEAD (default) or OBJECT
"""

argsp = argsubparsers.add_parser("tag", help="List and create tags")
argsp.add_argument(
    "-a",
    action="store_true",
    dest="create_tag_object",
    help="Whether to create a tag object",
)
argsp.add_argument("name", nargs="?", help="The new tag's name")
argsp.add_argument(
    "object", default="HEAD", nargs="?", help="The object the new tag will point to"
)


def cmd_tag(args):
    repo = repo_find()
    if args.name:
        tag_create(
            repo,
            args.name,
            args.object,
            type="object" if args.create_tag_object else "ref",
        )
    else:
        refs = ref_list(repo)
        show_ref(repo, refs["tags"], with_hash=False)


def tag_create(repo, name, ref, create_tag_object=False):
    # get the GitObject from the object reference
    sha = object_find(repo, ref)

    if create_tag_object:
        # create tag object (commit)
        tag = GitTag(repo)
        tag.kvlm = collections.OrderedDict()
        tag.kvlm[b"object"] = sha.encode()
        tag.kvlm[b"type"] = b"commit"
        tag.kvlm[b"tag"] = name.encode()
        tag.kvlm[b"tagger"] = b"wyag wyag@example.com"
        tag.kvlm[
            None
        ] = b"A tag generated by wyag, which won't\
            let you customize the message!"
        tag_sha = object_write(tag)
        # create reference
        ref_create(repo, "tags/" + name, tag_sha)
    else:
        # create lightweight tag (ref)
        ref_create(repo, "tags/" + name, sha)


def ref_create(repo, ref_name, sha):
    with open(repo_file(repo, "refs/" + ref_name), "w") as f:
        f.write(sha + "\n")


"""
what's a branch? The answer is actually surprisingly simple, 
but it may also end up being simply surprising: a branch is a 
reference to a commit. You could even say that a branch is a 
kind of a name for a commit. In this regard, a branch is exactly 
the same thing as a tag. Tags are refs that live in .git/refs/tags, 
branches are refs that live in .git/refs/heads.
"""
"""
1.Branches are references to a commit, tags can refer to any object;
2.Most importantly, the branch ref is updated at each commit. 
 This means that whenever you commit, Git actually does this:
    1)a new commit object is created, with the current branch's (commit!) ID as its parent;
    2)the commit object is hashed and stored;
    3)the branch ref is updated to refer to the new commit's hash.
"""


def object_resolve(repo, name):
    """Resolve name to an object hash in repo.

    This function is aware of:

     - the HEAD literal
        - short and long hashes
        - tags
        - branches
        - remote branches
        If name is HEAD, it will just resolve .git/HEAD;
        If name is a full hash, this hash is returned unmodified.
        If name looks like a short hash, it will collect objects whose full hash begin with this short hash.
        At last, it will resolve tags and branches matching name.
    """
    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")

    if not name.strip():  # empty string
        return None

    if name == "HEAD":
        return [ref_resolve(repo, "HEAD")]

    if hashRE.match(name):
        name = name.lower()
        prefix = name[0:2]
        path = repo_dir(repo, "objects", prefix, mkdir=False)
        if path:
            rem = name[2:]
            for f in os.listdir(path):
                if f.startswith(rem):
                    candidates.append(prefix + f)
    as_tag = ref_resolve(repo, "refs/tags" + name)
    if as_tag:
        candidates.append(as_tag)

    as_branch = ref_resolve(repo, "refs/heads/" + name)
    if as_branch:
        candidates.append(as_branch)

    return candidates


def object_find(repo, name, fmt=None, follow=True):
    """
    If we have a tag and fmt is anything else, we follow the tag.
    If we have a commit and fmt is tree, we return this commit's tree object
    In all other situations, we bail out: nothing else makes sense.
    """
    sha = object_resolve(repo, name)

    if not sha:
        raise Exception(f"No such reference {name}.")
    if len(sha) > 1:
        raise Exception(
            "Ambiguous reference {0}: Candidates \
                        are:\n - {1}.".format(
                name, "\n - ".join(sha)
            )
        )

    sha = sha[0]

    if not fmt:
        return sha

    while True:
        obj = object_read(repo, sha)
        if obj.fmt == fmt:
            return sha
        if not follow:
            return None
        if obj.fmt == b"tag":
            sha = obj.kvlm[b"object"].decode("ascii")
        elif obj.fmt == b"commit" and fmt == b"tree":
            sha = obj.kvlm[b"tree"].decode("ascii")
        else:
            return None


argsp = argsubparsers.add_parser(
    "rev-parse", help="Parse revision (or other objects) identifiers"
)
argsp.add_argument(
    "--wyag-type",
    metavar="type",
    dest="type",
    choices=["blob", "commit", "tag", "tree"],
    default=None,
    help="Specify the expected type",
)
argsp.add_argument("name", help="The name to parse")


def cmd_rev_parse(args):
    if args.type:
        fmt = args.type.encode()
    else:
        fmt = None
    repo = repo_find()
    print(object_find(repo, args.name, fmt, follow=True))


#! step8: the staging area and the index file
class GitIndexEntry(object):
    def __init__(
        self,
        ctime=None,
        mtime=None,
        dev=None,
        ino=None,
        mode_type=None,
        mode_perms=None,
        uid=None,
        gid=None,
        fsize=None,
        sha=None,
        flag_assume_valid=None,
        flag_stage=None,
        name=None,
    ):
        # the last time a file's metadata changed. this is a pair
        # (timestamp in seconds, nanoseconds)
        self.ctime = ctime
        # the last time a file's data changed. this is a pair
        # (timestamp in seconds, nanoseconds)
        self.mtime = mtime
        # the ID of device containing this file
        self.dev = dev
        # the file's inode number
        self.ino = ino
        # the object type, either b1000(regular), b1010(symlink),
        # b1110(gitlink)
        self.mode_type = mode_type
        # the object permissions, an integer
        self.mode_perms = mode_perms
        # user ID of owner
        self.uid = uid
        # group ID of owner
        self.gid = gid
        # size of this object, in bytes
        self.fsize = fsize
        # the object's SHA
        self.sha = sha
        self.flag_assume_valid = flag_assume_valid
        self.flag_stage = flag_stage
        # name of the object (full path this time!)
        self.name = name


class GitIndex(object):
    version = None
    entries = []

    def __init__(self, version=2, entries=None):
        if not entries:
            entries = list()

            self.version = version
            self.entries = entries


def index_read(repo):
    index_file = repo_file(repo, "index")

    if not os.path.exists(index_file):
        return GitIndex()

    with open(index_file, "rb") as f:
        raw = f.read()

    header = raw[:12]
    signature = header[:4]
    assert signature == b"DIRC"  # stands for "DirCache"
    version = int.from_bytes(header[4:8], "big")
    assert version == 2, "wyag only supports index file version 2"
    count = int.from_bytes(header[8:12], "big")

    entries = list()

    content = raw[12:]
    idx = 0
    for i in range(0, count):
        # Read creation time, as a unix timestamp (seconds since
        # 1970-01-01 00:00:00, the "epoch")
        ctime_s = int.from_bytes(content[idx : idx + 4], "big")
        # Read creation time, as nanoseconds after that timestamps,
        # for extra precision.
        ctime_ns = int.from_bytes(content[idx + 4 : idx + 8], "big")
        # Same for modification time: first seconds from epoch.
        mtime_s = int.from_bytes(content[idx + 8 : idx + 12], "big")
        # Then extra nanoseconds
        mtime_ns = int.from_bytes(content[idx + 12 : idx + 16], "big")
        # Device ID
        dev = int.from_bytes(content[idx + 16 : idx + 20], "big")
        # Inode
        ino = int.from_bytes(content[idx + 20 : idx + 24], "big")
        # Ignored.
        unused = int.from_bytes(content[idx + 24 : idx + 26], "big")
        assert 0 == unused
        mode = int.from_bytes(content[idx + 26 : idx + 28], "big")
        mode_type = mode >> 12
        assert mode_type in [0b1000, 0b1010, 0b1110]
        mode_perms = mode & 0b0000000111111111
        # User ID
        uid = int.from_bytes(content[idx + 28 : idx + 32], "big")
        # Group ID
        gid = int.from_bytes(content[idx + 32 : idx + 36], "big")
        # Size
        fsize = int.from_bytes(content[idx + 36 : idx + 40], "big")
        # SHA (object ID).  We'll store it as a lowercase hex string
        # for consistency.
        sha = format(int.from_bytes(content[idx + 40 : idx + 60], "big"), "040x")
        # Flags we're going to ignore
        flags = int.from_bytes(content[idx + 60 : idx + 62], "big")
        # Parse flags
        flag_assume_valid = (flags & 0b1000000000000000) != 0
        flag_extended = (flags & 0b0100000000000000) != 0
        assert not flag_extended
        flag_stage = flags & 0b0011000000000000
        # Length of the name.  This is stored on 12 bits, some max
        # value is 0xFFF, 4095.  Since names can occasionally go
        # beyond that length, git treats 0xFFF as meaning at least
        # 0xFFF, and looks for the final 0x00 to find the end of the
        # name --- at a small, and probably very rare, performance
        # cost.
        name_length = flags & 0b0000111111111111

        # We've read 62 bytes so far.
        idx += 62

        if name_length < 0xFFF:
            assert content[idx + name_length] == 0x00
            raw_name = content[idx : idx + name_length]
            idx += name_length + 1
        else:
            print("Notice: Name is 0x{:X} bytes long.".format(name_length))
            # This probably wasn't tested enough.  It works with a
            # path of exactly 0xFFF bytes.  Any extra bytes broke
            # something between git, my shell and my filesystem.
            null_idx = content.find(b"\x00", idx + 0xFFF)
            raw_name = content[idx:null_idx]
            idx = null_idx + 1

        # Just parse the name as utf8.
        name = raw_name.decode("utf-8")

        # Data is padded on multiples of eight bytes for pointer
        # alignment, so we skip as many bytes as we need for the next
        # read to start at the right position.

        idx = 8 * ceil(idx / 8)

        # And we add this entry to our list.
        entries.append(
            GitIndexEntry(
                ctime=(ctime_s, ctime_ns),
                mtime=(mtime_s, mtime_ns),
                dev=dev,
                ino=ino,
                mode_type=mode_type,
                mode_perms=mode_perms,
                uid=uid,
                gid=gid,
                fsize=fsize,
                sha=sha,
                flag_assume_valid=flag_assume_valid,
                flag_stage=flag_stage,
                name=name,
            )
        )

    return GitIndex(version=version, entries=entries)


argsp = argsubparsers.add_parser("ls-files", help="List all the stage files")
argsp.add_argument("--verbose", action="store_true", help="Show everything.")


def cmd_ls_files(args):
    repo = repo_find()
    index = index_read(repo)
    if args.verbose:
        print(
            "Index file format v{}, containing {} entries.".format(
                index.version, len(index.entries)
            )
        )

    for e in index.entries:
        print(e.name)
        if args.verbose:
            print(
                "  {} with perms: {:o}".format(
                    {0b1000: "regular file", 0b1010: "symlink", 0b1110: "git link"}[
                        e.mode_type
                    ],
                    e.mode_perms,
                )
            )
            print("  on blob: {}".format(e.sha))
            print(
                "  created: {}.{}, modified: {}.{}".format(
                    datetime.fromtimestamp(e.ctime[0]),
                    e.ctime[1],
                    datetime.fromtimestamp(e.mtime[0]),
                    e.mtime[1],
                )
            )
            print("  device: {}, inode: {}".format(e.dev, e.ino))
            print(
                "  user: {} ({})  group: {} ({})".format(
                    pwd.getpwuid(e.uid).pw_name,
                    e.uid,
                    grp.getgrgid(e.gid).gr_name,
                    e.gid,
                )
            )
            print(
                "  flags: stage={} assume_valid={}".format(
                    e.flag_stage, e.flag_assume_valid
                )
            )


# git status
argsp = argsubparsers.add_parser(
    "check-ignore", help="Check path(s) against ignore rules."
)
argsp.add_argument("path", nargs="+", help="Paths to check")


def cmd_check_ignore(args):
    repo = repo_find()
    rules = gitignore_read(repo)
    for path in args.path:
        if check_ignore(rules, path):
            print(path)


def gitignore_parse1(raw):
    raw = raw.strip()  # Remove leading/trailing spaces

    if not raw or raw[0] == "#":
        return None
    elif raw[0] == "!":
        return (raw[1:], False)
    elif raw[0] == "\\":
        return (raw[1:], True)
    else:
        return (raw, True)


def gitignore_parse(lines):
    ret = list()

    for line in lines:
        parsed = gitignore_parse1(line)
        if parsed:
            ret.append(parsed)

    return ret


class GitIgnore(object):
    absolute = None
    scoped = None

    def __init__(self, absolute, scoped):
        self.absolute = absolute
        self.scoped = scoped


def gitignore_read(repo):
    ret = GitIgnore(absolute=list(), scoped=dict())

    # Read local configuration in .git/info/exclude
    repo_file = os.path.join(repo.gitdir, "info/exclude")
    if os.path.exists(repo_file):
        with open(repo_file, "r") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))

    # Global configuration
    if "XDG_CONFIG_HOME" in os.environ:
        config_home = os.environ["XDG_CONFIG_HOME"]
    else:
        config_home = os.path.expanduser("~/.config")
    global_file = os.path.join(config_home, "git/ignore")

    if os.path.exists(global_file):
        with open(global_file, "r") as f:
            ret.absolute.append(gitignore_parse(f.readlines()))

    # .gitignore files in the index
    index = index_read(repo)

    for entry in index.entries:
        if entry.name == ".gitignore" or entry.name.endswith("/.gitignore"):
            dir_name = os.path.dirname(entry.name)
            contents = object_read(repo, entry.sha)
            lines = contents.blobdata.decode("utf8").splitlines()
            ret.scoped[dir_name] = gitignore_parse(lines)
    return ret


def check_ignore1(rules, path):
    result = None
    for pattern, value in rules:
        if fnmatch(path, pattern):
            result = value
    return result


def check_ignore_scoped(rules, path):
    parent = os.path.dirname(path)
    while True:
        if parent in rules:
            result = check_ignore1(rules[parent], path)
            if result != None:
                return result
        if parent == "":
            break
        parent = os.path.dirname(parent)
    return None


def check_ignore_absolute(rules, path):
    parent = os.path.dirname(path)
    for ruleset in rules:
        result = check_ignore1(ruleset, path)
        if result != None:
            return result
    return False  # This is a reasonable default at this point.


def check_ignore(rules, path):
    if os.path.isabs(path):
        raise Exception(
            "This function requires path to be relative to the repository's root"
        )

    result = check_ignore_scoped(rules.scoped, path)
    if result != None:
        return result

    return check_ignore_absolute(rules.absolute, path)


# status command
argsp = argsubparsers.add_parser("status", help="Show the working tree status.")


def cmd_status(_):
    repo = repo_find()
    index = index_read(repo)

    cmd_status_branch(repo)
    cmd_status_head_index(repo, index)
    print()
    cmd_status_index_worktree(repo, index)


def branch_get_active(repo):
    with open(repo_file(repo, "HEAD"), "r") as f:
        head = f.read()

    if head.startswith("ref: refs/heads/"):
        return head[16:-1]
    else:
        return False


def cmd_status_branch(repo):
    branch = branch_get_active(repo)
    if branch:
        print("On branch {}.".format(branch))
    else:
        print("HEAD detached at {}".format(object_find(repo, "HEAD")))


def tree_to_dict(repo, ref, prefix=""):
    ret = dict()
    tree_sha = object_find(repo, ref, fmt=b"tree")
    tree = object_read(repo, tree_sha)

    for leaf in tree.items:
        full_path = os.path.join(prefix, leaf.path)

        # We read the object to extract its type (this is uselessly
        # expensive: we could just open it as a file and read the
        # first few bytes)
        is_subtree = leaf.mode.startswith(b"04")

        # Depending on the type, we either store the path (if it's a
        # blob, so a regular file), or recurse (if it's another tree,
        # so a subdir)
        if is_subtree:
            ret.update(tree_to_dict(repo, leaf.sha, full_path))
        else:
            ret[full_path] = leaf.sha

    return ret


def cmd_status_head_index(repo, index):
    print("Changes to be committed:")

    head = tree_to_dict(repo, "HEAD")
    for entry in index.entries:
        if entry.name in head:
            if head[entry.name] != entry.sha:
                print("  modified:", entry.name)
            del head[entry.name]  # Delete the key
        else:
            print("  added:   ", entry.name)

    # Keys still in HEAD are files that we haven't met in the index,
    # and thus have been deleted.
    for entry in head.keys():
        print("  deleted: ", entry)


def cmd_status_index_worktree(repo, index):
    print("Changes not staged for commit:")

    ignore = gitignore_read(repo)

    gitdir_prefix = repo.gitdir + os.path.sep

    all_files = list()

    # We begin by walking the filesystem
    for root, _, files in os.walk(repo.worktree, True):
        if root == repo.gitdir or root.startswith(gitdir_prefix):
            continue
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, repo.worktree)
            all_files.append(rel_path)

    # We now traverse the index, and compare real files with the cached
    # versions.

    for entry in index.entries:
        full_path = os.path.join(repo.worktree, entry.name)

        # That file *name* is in the index

        if not os.path.exists(full_path):
            print("  deleted: ", entry.name)
        else:
            stat = os.stat(full_path)

            # Compare metadata
            ctime_ns = entry.ctime[0] * 10**9 + entry.ctime[1]
            mtime_ns = entry.mtime[0] * 10**9 + entry.mtime[1]
            if (stat.st_ctime_ns != ctime_ns) or (stat.st_mtime_ns != mtime_ns):
                # If different, deep compare.
                # @FIXME This *will* crash on symlinks to dir.
                with open(full_path, "rb") as fd:
                    new_sha = object_hash(fd, b"blob", None)
                    # If the hashes are the same, the files are actually the same.
                    same = entry.sha == new_sha

                    if not same:
                        print("  modified:", entry.name)

        if entry.name in all_files:
            all_files.remove(entry.name)

    print()
    print("Untracked files:")

    for f in all_files:
        # @TODO If a full directory is untracked, we should display
        # its name without its contents.
        if not check_ignore(ignore, f):
            print(" ", f)


#! step9: staging and committing
def index_write(repo, index):
    with open(repo_file(repo, "index"), "wb") as f:
        # HEADER

        # Write the magic bytes.
        f.write(b"DIRC")
        # Write version number.
        f.write(index.version.to_bytes(4, "big"))
        # Write the number of entries.
        f.write(len(index.entries).to_bytes(4, "big"))

        # ENTRIES

        idx = 0
        for e in index.entries:
            f.write(e.ctime[0].to_bytes(4, "big"))
            f.write(e.ctime[1].to_bytes(4, "big"))
            f.write(e.mtime[0].to_bytes(4, "big"))
            f.write(e.mtime[1].to_bytes(4, "big"))
            f.write(e.dev.to_bytes(4, "big"))
            f.write(e.ino.to_bytes(4, "big"))

            # Mode
            mode = (e.mode_type << 12) | e.mode_perms
            f.write(mode.to_bytes(4, "big"))

            f.write(e.uid.to_bytes(4, "big"))
            f.write(e.gid.to_bytes(4, "big"))

            f.write(e.fsize.to_bytes(4, "big"))
            # @FIXME Convert back to int.
            f.write(int(e.sha, 16).to_bytes(20, "big"))

            flag_assume_valid = 0x1 << 15 if e.flag_assume_valid else 0

            name_bytes = e.name.encode("utf8")
            bytes_len = len(name_bytes)
            if bytes_len >= 0xFFF:
                name_length = 0xFFF
            else:
                name_length = bytes_len

            # We merge back three pieces of data (two flags and the
            # length of the name) on the same two bytes.
            f.write((flag_assume_valid | e.flag_stage | name_length).to_bytes(2, "big"))

            # Write back the name, and a final 0x00.
            f.write(name_bytes)
            f.write((0).to_bytes(1, "big"))

            idx += 62 + len(name_bytes) + 1

            # Add padding if necessary.
            if idx % 8 != 0:
                pad = 8 - (idx % 8)
                f.write((0).to_bytes(pad, "big"))
                idx += pad


argsp = argsubparsers.add_parser(
    "rm", help="Remove files from the working tree and the index."
)
argsp.add_argument("path", nargs="+", help="Files to remove")


def cmd_rm(args):
    repo = repo_find()
    rm(repo, args.path)


def rm(repo, paths, delete=True, skip_missing=False):
    # Find and read the index
    index = index_read(repo)

    worktree = repo.worktree + os.sep

    # Make paths absolute
    abspaths = list()
    for path in paths:
        abspath = os.path.abspath(path)
        if abspath.startswith(worktree):
            abspaths.append(abspath)
        else:
            raise Exception("Cannot remove paths outside of worktree: {}".format(paths))

    kept_entries = list()
    remove = list()

    for e in index.entries:
        full_path = os.path.join(repo.worktree, e.name)

        if full_path in abspaths:
            remove.append(full_path)
            abspaths.remove(full_path)
        else:
            kept_entries.append(e)  # Preserve entry

    if len(abspaths) > 0 and not skip_missing:
        raise Exception("Cannot remove paths not in the index: {}".format(abspaths))

    if delete:
        for path in remove:
            os.unlink(path)

    index.entries = kept_entries
    index_write(repo, index)


# add command
argsp = argsubparsers.add_parser("add", help="Add files contents to the index.")
argsp.add_argument("path", nargs="+", help="Files to add")


def cmd_add(args):
    repo = repo_find()
    add(repo, args.path)


def add(repo, paths, delete=True, skip_missing=False):
    # First remove all paths from the index, if they exist.
    rm(repo, paths, delete=False, skip_missing=True)

    worktree = repo.worktree + os.sep

    # Convert the paths to pairs: (absolute, relative_to_worktree).
    # Also delete them from the index if they're present.
    clean_paths = list()
    for path in paths:
        abspath = os.path.abspath(path)
        if not (abspath.startswith(worktree) and os.path.isfile(abspath)):
            raise Exception("Not a file, or outside the worktree: {}".format(paths))
        relpath = os.path.relpath(abspath, repo.worktree)
        clean_paths.append((abspath, relpath))

        # Find and read the index.  It was modified by rm.  (This isn't
        # optimal, good enough for wyag!)
        #
        # @FIXME, though: we could just
        # move the index through commands instead of reading and writing
        # it over again.
        index = index_read(repo)

        for abspath, relpath in clean_paths:
            with open(abspath, "rb") as fd:
                sha = object_hash(fd, b"blob", repo)

            stat = os.stat(abspath)

            ctime_s = int(stat.st_ctime)
            ctime_ns = stat.st_ctime_ns % 10**9
            mtime_s = int(stat.st_mtime)
            mtime_ns = stat.st_mtime_ns % 10**9

            entry = GitIndexEntry(
                ctime=(ctime_s, ctime_ns),
                mtime=(mtime_s, mtime_ns),
                dev=stat.st_dev,
                ino=stat.st_ino,
                mode_type=0b1000,
                mode_perms=0o644,
                uid=stat.st_uid,
                gid=stat.st_gid,
                fsize=stat.st_size,
                sha=sha,
                flag_assume_valid=False,
                flag_stage=False,
                name=relpath,
            )
            index.entries.append(entry)

        # Write the index back
        index_write(repo, index)


# commit command
argsp = argsubparsers.add_parser("commit", help="Record changes to the repository.")

argsp.add_argument(
    "-m",
    metavar="message",
    dest="message",
    help="Message to associate with this commit.",
)


def gitconfig_read():
    xdg_config_home = (
        os.environ["XDG_CONFIG_HOME"]
        if "XDG_CONFIG_HOME" in os.environ
        else "~/.config"
    )
    configfiles = [
        os.path.expanduser(os.path.join(xdg_config_home, "git/config")),
        os.path.expanduser("~/.gitconfig"),
    ]

    config = configparser.ConfigParser()
    config.read(configfiles)
    return config


def gitconfig_user_get(config):
    if "user" in config:
        if "name" in config["user"] and "email" in config["user"]:
            return "{} <{}>".format(config["user"]["name"], config["user"]["email"])
    return None


def tree_from_index(repo, index):
    contents = dict()
    contents[""] = list()

    # Enumerate entries, and turn them into a dictionary where keys
    # are directories, and values are lists of directory contents.
    for entry in index.entries:
        dirname = os.path.dirname(entry.name)

        # We create all dictonary entries up to root ("").  We need
        # them *all*, because even if a directory holds no files it
        # will contain at least a tree.
        key = dirname
        while key != "":
            if not key in contents:
                contents[key] = list()
            key = os.path.dirname(key)

        # For now, simply store the entry in the list.
        contents[dirname].append(entry)

    # Get keys (= directories) and sort them by length, descending.
    # This means that we'll always encounter a given path before its
    # parent, which is all we need, since for each directory D we'll
    # need to modify its parent P to add D's tree.
    sorted_paths = sorted(contents.keys(), key=len, reverse=True)

    # This variable will store the current tree's SHA-1.  After we're
    # done iterating over our dict, it will contain the hash for the
    # root tree.
    sha = None

    # We ge through the sorted list of paths (dict keys)
    for path in sorted_paths:
        # Prepare a new, empty tree object
        tree = GitTree()

        # Add each entry to our new tree, in turn
        for entry in contents[path]:
            # An entry can be a normal GitIndexEntry read from the
            # index, or a tree we've created.
            if isinstance(entry, GitIndexEntry):  # Regular entry (a file)
                # We transcode the mode: the entry stores it as integers,
                # we need an octal ASCII representation for the tree.
                leaf_mode = "{:02o}{:04o}".format(
                    entry.mode_type, entry.mode_perms
                ).encode("ascii")
                leaf = GitTreeLeaf(
                    mode=leaf_mode, path=os.path.basename(entry.name), sha=entry.sha
                )
            else:  # Tree.  We've stored it as a pair: (basename, SHA)
                leaf = GitTreeLeaf(mode=b"040000", path=entry[0], sha=entry[1])

            tree.items.append(leaf)

        # Write the new tree object to the store.
        sha = object_write(tree, repo)

        # Add the new tree hash to the current dictionary's parent, as
        # a pair (basename, SHA)
        parent = os.path.dirname(path)
        base = os.path.basename(
            path
        )  # The name without the path, eg main.go for src/main.go
        contents[parent].append((base, sha))

    return sha


def commit_create(repo, tree, parent, author, timestamp, message):
    commit = GitCommit()  # Create the new commit object.
    commit.kvlm[b"tree"] = tree.encode("ascii")
    if parent:
        commit.kvlm[b"parent"] = parent.encode("ascii")

    # Format timezone
    offset = int(timestamp.astimezone().utcoffset().total_seconds())
    hours = offset // 3600
    minutes = (offset % 3600) // 60
    tz = "{}{:02}{:02}".format("+" if offset > 0 else "-", hours, minutes)

    author = author + timestamp.strftime(" %s ") + tz

    commit.kvlm[b"author"] = author.encode("utf8")
    commit.kvlm[b"committer"] = author.encode("utf8")
    commit.kvlm[None] = message.encode("utf8")

    return object_write(commit, repo)


def cmd_commit(args):
    repo = repo_find()
    index = index_read(repo)
    # Create trees, grab back SHA for the root tree.
    tree = tree_from_index(repo, index)

    # Create the commit object itself
    commit = commit_create(
        repo,
        tree,
        object_find(repo, "HEAD"),
        gitconfig_user_get(gitconfig_read()),
        datetime.now(),
        args.message,
    )

    # Update HEAD so our commit is now the tip of the active branch.
    active_branch = branch_get_active(repo)
    if active_branch:  # If we're on a branch, we update refs/heads/BRANCH
        with open(
            repo_file(repo, os.path.join("refs/heads", active_branch)), "w"
        ) as fd:
            fd.write(commit + "\n")
    else:  # Otherwise, we update HEAD itself.
        with open(repo_file(repo, "HEAD"), "w") as fd:
            fd.write("\n")
