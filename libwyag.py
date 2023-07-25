'''
We’ll begin by creating the binary. Create a new file called wyag in your text editor, and copy the following few lines:
{
    #!/usr/bin/env python3

    import libwyag
    libwyag.main()
}
Then make it executable:

    $ chmod +x wyag
You’re done!
'''

# 1.import modules
import argparse  # to parse command-line arguments.
import collections # more container types, most notably an OrderedDict
import configparser  # parse configuration file format, basically Microsoft’s INI format
import hashlib  # Git uses the SHA-1 function quite extensively
import os  # os and os.path
import re  # use a bit regular expressions
import sys  # to access the actual command-line arguments in sys.argv
import zlib  # Git compresses everything using zlib

# 2.initialize
argparser = argparse.ArgumentParser(description="The stupid content tracker.")
# subparsers to handle subcommands(as in git: init, commit)
argsubparsers = argparser.add_subparsers(title="Commands", dest="command")
argsubparsers.required = True
# ?: Can I directly use [argparser.add_subparsers(title="Commands", dest="command").required = True]

"""
The dest="command" argument states that the name of the chosen subparser will be returned as a string in a field
called command. So we just need to read this string and call the correct function accordingly. By convention, I’ll
prefix these functions by cmd_. cmd_* functions take the parsed arguments as their unique parameter, and are
responsible for processing and validating them before executing the actual command.
"""


# 3.define main function
def main(argv=sys.argv[1:]):
    # ?: Why not [args = argparser.parse_args(sys.argv[1:])]
    args = argparser.parse_args(argv)

    if   args.command == "add"         : cmd_add(args)
    elif args.command == "cat-file"    : cmd_cat_file(args)
    elif args.command == "checkout"    : cmd_checkout(args)
    elif args.command == "commit"      : cmd_commit(args)
    elif args.command == "hash-object" : cmd_hash_object(args)
    elif args.command == "init"        : cmd_init(args)
    elif args.command == "log"         : cmd_log(args)
    elif args.command == "ls-tree"     : cmd_ls_tree(args)
    elif args.command == "merge"       : cmd_merge(args)
    elif args.command == "rebase"      : cmd_rebase(args)
    elif args.command == "rev-parse"   : cmd_rev_parse(args)
    elif args.command == "rm"          : cmd_rm(args)
    elif args.command == "show-ref"    : cmd_show_ref(args)
    elif args.command == "tag"         : cmd_tag(args)


# 4.git: init
class GitRepository(object):
    """A git repository"""

    worktree = None
    gitdir = None
    conf = None

    def __int__(self, path, force=False):
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.exists(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")  # ?: why need param self  A: it isn't a method of the class

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion {vers}")


# ?: Why not attach these repo_* function to the class GitRepository
# a general path building function
def repo_path(repo: GitRepository, *path):
    """Compute path under repo's gitdir"""
    '''可变参数知识点：
    函数定义时，*args使传入的多参数变成args元组。（这只是表明args是可变参数）
    而在其它地方，*会将一个列表或元组拆解成所有元素
    如：print(*(1,2,3)) --> 1 2 3
    传递参数时：*[1,2,3] == 1,2,3(虽然实际没有逗号,但它就是代表三个参数)
    [*[1,2,3]] == [1,2,3]
    '''
    return os.path.join(repo.gitdir, *path)  # in function, {*path} is same as {''.join(path)}


def repo_file(repo, *path, mkdir=False):
    """Same as repo_path, but create dirname(*path) if absent.  For
example, repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\") will create
.git/refs/remotes/origin."""
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)


def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path, but mkdir *path if absent if mkdir."""
    path = repo_path(repo, *path)
    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception("Not a directory {path}")
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None





















