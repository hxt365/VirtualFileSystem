from django.core.exceptions import ValidationError
from django.db import DataError
from django.test import TestCase

from . import repositories as repo, services as cache
from .exceptions import FileNotFound, FileExisted, InvalidFilename, MovedIntoSubFolder
from .models import FilePath, File


class BaseTestCase(TestCase):
    databases = '__all__'

    def tearDown(self):
        cache.r.flushall()


class FilePathTestCase(BaseTestCase):
    def test_valid_filepath(self):
        valid_paths = [
            '/abc',
            '/a/b/c',
            '/a/b/c/',
            '/a_b/ /hxt365'
            '/sth/ok- /okokok/',
            '/a/./../b/./',
            '////',
        ]
        for path in valid_paths:
            try:
                FilePath(raw_path=path)
            except FileNotFound:
                self.fail('FilePath raised exceptions unexpectedly')

    def test_invalid_filepath(self):
        invalid_paths = [
            '',
            '$hello',
            '\\',
            '/a/^/b',
        ]
        for path in invalid_paths:
            try:
                FilePath(raw_path=path)
                self.fail('FilePath did not raise exceptions as expected')
            except FileNotFound:
                pass

    def test_get_parent_dir(self):
        filepaths = [
            ('/a/b/c', '/a/b'),
            ('/a/b/c/', '/a/b'),
            ('//', '/'),
            ('/', '/'),
        ]
        for filepath in filepaths:
            self.assertEqual(FilePath(filepath[0]).parent().path, filepath[1])

    def test_get_dirs(self):
        filepaths = [
            ('/a/b/c', ['a', 'b', 'c']),
            ('/a/b/c/', ['a', 'b', 'c']),
            ('//', []),
            ('/', []),
        ]
        for filepath in filepaths:
            self.assertEqual(FilePath(filepath[0]).dirs(), filepath[1])


class FileModelTestCase(BaseTestCase):
    def setUp(self) -> None:
        self.root = repo._get_root_directory()

    def test_create_files_then_success(self):
        file1 = File(name='test 1', is_folder=False, data='hello world')
        file2 = File(name='test 2', is_folder=False, data='hello world')
        folder = File(name='test 3', is_folder=True)

        self.root.add_child(file1)
        self.root.add_child(folder)
        folder.add_child(file2)
        self.assertTrue(file1 in self.root.get_children())
        self.assertTrue(folder in self.root.get_children())
        self.assertTrue(file2 in folder.get_children())

    def test_create_duplicated_files_then_fail(self):
        file1 = File(name='test', is_folder=False, data='hello world')
        file2 = File(name='test', is_folder=False, data='hello world')
        try:
            self.root.add_child(file1)
            self.root.add_child(file2)
            self.fail('creating duplicated files in one folder should fail')
        except FileExisted:
            pass

    def test_create_files_with_invalid_name_then_fail(self):
        invalid_names = [
            '$',
            '\\',
            'abc/',
            '',
            'a' * 256,
        ]
        for name in invalid_names:
            try:
                File(name=name, is_folder=True, parent=self.root).save()
                self.fail('invalid name should fail')
            except (InvalidFilename, DataError):
                pass

    def test_create_files_without_parent_then_fail(self):
        try:
            File(name='test', is_folder=True).save()
            self.fail('create file without parent should fail')
        except ValidationError:
            pass

    def test_remove_files_then_success(self):
        file1 = File(name='test 1', is_folder=False, data='hello world')
        file2 = File(name='test 2', is_folder=True)
        self.root.add_child(file1)
        self.root.add_child(file2)
        try:
            self.root.remove_child(filename=file1.name)
            self.root.remove_child(filename=file2.name)
        except FileNotFound:
            self.fail('should delete successfully')

    def test_timestamp_created_correctly(self):
        self.assertTrue(self.root.created_at is not None)

    def test_timestamp_updated_correctly(self):
        file = File(name='file', is_folder=False, data='hello world')
        # Create a child file in root directory
        self.root.refresh_from_db()
        old_timestamp = self.root.updated_at
        self.root.add_child(file)
        self.root.refresh_from_db()
        new_timestamp = self.root.updated_at
        self.assertTrue(old_timestamp < new_timestamp)
        # Delete the file in root directory
        self.root.refresh_from_db()
        old_timestamp = self.root.updated_at
        self.root.remove_child(file.name)
        self.root.refresh_from_db()
        new_timestamp = self.root.updated_at
        self.assertTrue(old_timestamp < new_timestamp)

    def test_get_size_of_file(self):
        file1 = File(name='test 1', is_folder=False, data='123')
        file2 = File(name='test 2', is_folder=False, data='12345')
        file3 = File(name='test 3', is_folder=False, data='12')
        file4 = File(name='test 4', is_folder=False, data='1')
        folder1 = File(name='test 5', is_folder=True)
        folder2 = File(name='test 6', is_folder=True)
        self.root.add_child(file1)
        self.root.add_child(folder1)
        self.root.add_child(folder2)
        folder1.add_child(file2)
        folder1.add_child(file3)
        folder2.add_child(file4)
        self.assertEqual(self.root.size, 11)
        self.assertEqual(file1.size, 3)
        self.assertEqual(folder1.size, 7)


class FileRepositoryTestCase(BaseTestCase):
    def setUp(self) -> None:
        root = repo._get_root_directory()
        folder1 = File(name='f1', is_folder=True)
        root.add_child(folder1)
        folder2 = File(name='f2', is_folder=True)
        folder1.add_child(folder2)
        folder3 = File(name=' ', is_folder=True)
        folder2.add_child(folder3)
        file = File(name='test-1', is_folder=False, data='test')
        folder3.add_child(file)
        folder4 = File(name=' ', is_folder=True)
        root.add_child(folder4)

    def test_get_file_then_success(self):
        try:
            filepaths = [
                '/f1/f2/ /test-1',
                '/f1/f2/ /test-1/',
                '/f1/f2/ /./../../f2/ /test-1',
                '/f1/f2/ /./../../f2/ /',
                '/f1/f2/ /./../../f2/',
                '/f1',
                '/',
                '/f1/f2/ /test-1/../',
                '/f1/f2/ /test-1/./',
            ]
            for filepath in filepaths:
                _ = repo.get_file(filepath=FilePath(filepath))
        except FileNotFound:
            self.fail('should get file successfully')

    def test_get_file_then_fail(self):
        filepaths = [
            '/f1/f2/ /./../../f1/ /test-1',
            '/f1/test-1',
        ]
        for filepath in filepaths:
            try:
                _ = repo.get_file(filepath=FilePath(filepath))
                self.fail('should get file then fail')
            except FileNotFound:
                pass

    def test_create_file_then_sucess(self):
        files = [
            ('/f1/f2/ /test-2', False, 'test'),
            ('/f1/f2/ /test-3', True, 'test'),
            ('/f1/f2/ /f3/', False, None),
            ('/f1/f2/ /f4/', True, None),
            ('/f1/f2/f3/f4/test', True, 'test'),
            ('/f1/f2/f3/f4/f5', True, 'test'),
            ('/f1/f2/test-2/', False, 'test'),
            ('/f1/f2/test-3/', True, 'test'),
        ]
        for (filepath, p_flag, data) in files:
            try:
                repo.create_file(filepath=FilePath(filepath), p_flag=p_flag, data=data)
                repo.get_file(filepath=FilePath(filepath))
            except (FileNotFound, FileExisted):
                self.fail('should create file successfully')

    def test_create_file_then_fail(self):
        files = [
            ('/f1/f2/ /f3/$#/f', False, None),
            ('/f1/f2/ /test-1', True, 'test'),
        ]
        for (filepath, p_flag, data) in files:
            try:
                repo.create_file(filepath=FilePath(filepath), p_flag=p_flag, data=data)
                self.fail('should fail when create file ')
            except (FileNotFound, FileExisted):
                pass

    def test_update_file_then_success(self):
        repo.update_file(FilePath('/f1/f2/ /test-1'), 'test-2', 'ABC')
        file = repo.get_file(FilePath('/f1/f2/ /test-2'))
        self.assertEqual(file.data, 'ABC')

        repo.update_file(FilePath('/f1/f2/'), 'f3')
        repo.update_file(FilePath('/f1/f3/'), 'f4', 'test')
        _ = repo.get_file(FilePath('/f1/f4/ /test-2'))

    def test_update_file_then_fail(self):
        files = [
            ('/f1/f3/ /test-1', 'a', None),
            ('/f1/f2/ /test-1', 'a#', None),
            ('/f1/f2/ /test-1', 'a#', 'test'),
        ]
        for (filepath, name, data) in files:
            try:
                repo.update_file(filepath=FilePath(filepath), new_name=name, new_data=data)
                self.fail('should fail when update file ')
            except (FileNotFound, FileExisted, InvalidFilename):
                pass

    def test_delete_file_then_success(self):
        repo.remove_file([FilePath('/f1/f2/ /test-1'), FilePath('/f1')])
        try:
            repo.get_file(FilePath('/f1/f2/'))
            self.fail('should fail when update file ')
        except (FileNotFound, FileExisted):
            pass

    def test_delete_file_then_fail(self):
        try:
            repo.remove_file([FilePath('/f1/f2/'), FilePath('/f1/f2/ /test-1')])
            self.fail('should fail when delete file ')
        except (FileNotFound, FileExisted):
            pass

    def test_move_file_then_success(self):
        repo.move_file(FilePath('/f1/f2/ /test-1'), FilePath('/f1/f2/'))
        _ = repo.get_file(FilePath('/f1/f2/test-1'))
        repo.move_file(FilePath('/f1/f2/'), FilePath('/'))
        _ = repo.get_file(FilePath('/f2/test-1'))
        try:
            _ = repo.get_file(FilePath('/f1/f2/test-1'))
            self.fail('should fail when get file ')
        except (FileNotFound, FileExisted):
            pass

    def test_move_file_then_fail(self):
        filepaths = [
            ('/f1/f2/ /test-1', '/f1/f2/f3/'),
            ('/f1/f2/ /', '/f1/f2/ /test-1'),
            ('/4/', '/f1/f2/ /test-1'),
        ]
        for (src, dest) in filepaths:
            try:
                repo.move_file(FilePath(src), FilePath(dest))
                self.fail('should fail when get file ')
            except (FileNotFound, FileExisted, MovedIntoSubFolder):
                pass

    def test_find_then_success(self):
        file_tree = [
            ('/abc/abcd/test/aAa', False),
            ('/def/abc/kkk/ad/', True)
        ]
        for filepath, is_folder in file_tree:
            repo.create_file(FilePath(filepath), p_flag=True, data='test' if not is_folder else None)
        tests = [
            (('/', 'a', None), [
                '/abc/',
                '/abc/abcd/',
                '/abc/abcd/test/aAa',
                '/def/abc/',
                '/def/abc/kkk/ad/'
            ]),
            (('/', 'a', 2), [
                '/abc/',
                '/abc/abcd/',
                '/def/abc/',
            ]),
            (('/def', 'a', None), [
                '/def/abc/',
                '/def/abc/kkk/ad/'
            ]),
            (('/', 'z', None), []),
            (('/', '/', None), []),
            (('/', '', 2), [
                '/',
                '/ /',
                '/abc/',
                '/abc/abcd/',
                '/def/',
                '/def/abc/',
                '/f1/',
                '/f1/f2/',
            ]),
            (('/abc/', '', None), [
                '/abc/',
                '/abc/abcd/',
                '/abc/abcd/test/',
                '/abc/abcd/test/aAa'
            ]),
        ]
        for (filepath, name, level), result in tests:
            self.assertEqual(repo.find(name=name, folder_path=FilePath(filepath), max_level=level),
                             result)

    def test_find_then_fail(self):
        data = [
            ('/f1/f2/ /test-1', 't'),
            ('/f3/', 'f'),
        ]
        for filepath, name in data:
            try:
                repo.find(name=name, folder_path=FilePath(filepath))
                self.fail('should fail when find files in folder')
            except FileNotFound:
                pass
