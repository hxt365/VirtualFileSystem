# Virtual File System (VFS)

In this project, I built a simple web-based file system, that contains only folders and files.
Each folder itself is a group of file(s) and folder(s). The VFS must provide following interfaces:
1. `cd FOLDER_PATH`: change current working directory/folder to the specified `FOLDER`
2. `cr [-p] PATH [DATA]`: create a new file (if `DATA` is specified, otherwise create a new folder) at the specified `PATH`
3. `cat FILE_PATH`: show the content of a file at `FILE_PATH`. If there is no file at `FILE_PATH`, raise error.
4. `ls [FOLDER_PATH]`: list out all items **directly under** a folder
5. `find NAME [FOLDER_PATH]`: search all files/folders whose name **contains** the substring `NAME`.
7. `mv PATH FOLDER_PATH` move a file/folder at `PATH` **into** the destination `FOLDER_PATH`. 
8. `rm PATH [PATH2 PATH3...]`: remove files/folders at the specified `PATH`(s)

## You can run
```bash
  git clone https://github.com/hxt365/VirtualFileSystem.git
  cd VirtualFileSystem
  docker-compose up --build
```

## Design decisions
Assuming:
- Workload is balanced, neither write-heavy nor read-heavy.
- VFS must guarantee consistency.
- VFS must take care of concurrent transactions.
- Performance should be reasonably good.

First, VFS is inspired by Unix file system, in which folders are just a special type of file.
Each file/folder has a unique ID and every file/folder has one and only one parent folder, except root folder, that has no parent. 
So we can easily store files with one-many relation in RDBMS. Besides, that, storing and accessing files/folders by absolute paths seems fast, 
as they are all different, but to guarantee consistency when updating filename or moving files around, we also have to update all children within the files being updated.
To take it further, during concurrent transactions, we have to acquire exclusive locks on all files being updated, which causes performance dramatically downgraded.
Hence, it's better to avoid storing absolute path in DB.  
Second, we represent VFS as tree data structure. To retrieve a file/folder, we follow down its absolute path. In order to accelerate accessing speed
and balance out the workload, we have a cache of VFS on Redis. In this project, I assume that operations with cache are atomic, but in reality server can
crash during populating or invalidating cache, and we should do something more sophisticated, such as using workers  with events from DB log to 
invalidate cache. (For this part I have not done yet).  
Next, there are a lot of issues about consistency with concurrent transactions. For example, deleting a folder requires cascading deletion
of all of its children, if atomicity is not preserved then orphan files/folders may exist. For another example, 
during process of adding a file into a folder, the folder may be deleted by a concurrent transaction.
In order to solve concurrency problems, I use Repeatable Read isolation level. Please see comments and code in the project
for more detail of how I solved each problem.  
Finally, about API, REST was used because it's stateless, cacheable, popular, and is supported by a lot of libraries and frameworks,
hence VFS can scale better.  
By convention, REST API should be nouns, not verbs. But in this project, I used verbs for API because it's easier for users to
think of commands that way.  

See comments and code for more details.


## Tech stacks
- Django
- Django Rest Framework
- Redis
- PostgreSQL

## Test coverage:
```
Name                                    Stmts   Miss  Cover
-----------------------------------------------------------
VirtualFileSystem/__init__.py               0      0   100%
VirtualFileSystem/asgi.py                   4      4     0%
VirtualFileSystem/settings.py              24      0   100%
VirtualFileSystem/urls.py                   3      0   100%
VirtualFileSystem/wsgi.py                   4      4     0%
filesystem/__init__.py                      0      0   100%
filesystem/admin.py                         3      0   100%
filesystem/api/serializers.py              38      0   100%
filesystem/api/test.py                    135      0   100%
filesystem/api/urls.py                      4      0   100%
filesystem/api/utils.py                     7      0   100%
filesystem/api/views.py                    89      4    96%
filesystem/apps.py                          3      3     0%
filesystem/exceptions.py                    5      0   100%
filesystem/migrations/0001_initial.py       6      0   100%
filesystem/migrations/__init__.py           0      0   100%
filesystem/models.py                       98      8    92%
filesystem/repositories.py                 88      6    93%
filesystem/tests.py                       215    215     0%
manage.py                                  12      2    83%
-----------------------------------------------------------
TOTAL                                     738    246    67%
```

## Links
1. [VFS Terminal](https://github.com/hxt365/terminal) - Front-end part of the project.