
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


