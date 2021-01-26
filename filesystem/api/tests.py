from collections import OrderedDict

from rest_framework import status
from rest_framework.reverse import reverse as api_reverse
from rest_framework.test import APITestCase

from filesystem import repositories as repo
from filesystem import services as cache
from filesystem.models import FilePath


class BaseAPITestCase(APITestCase):
    databases = '__all__'

    def setUp(self) -> None:
        cache.r.flushall()
        self._setUp()

    def _setUp(self) -> None:
        raise NotImplementedError

    def tearDown(self) -> None:
        cache.r.flushall()


class CdAPITestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:cd')
        repo.create_file(FilePath('/f1/f2/f3/test'), p_flag=True, data='test')
        repo.create_file(FilePath('/f1/f4/test'), p_flag=True, data='test')

    def test_cd_then_200_OK(self):
        folder_paths = ['/f1/f2/f3/', '/f1/f4/', '/']
        for path in folder_paths:
            res = self.client.post(self.URL, data={'folder_path': path}, format='json')
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data, {'folder_path': FilePath(path).path + '/' if path != '/' else '/'})

    def test_cd_then_400_BAD_REQUEST(self):
        folder_paths = ['/f1/f2/f3/test', '/f1/f3/', '/' * 501, None]
        for path in folder_paths:
            res = self.client.post(self.URL, data={'folder_path': path}, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class CrAPITestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:cr')

    def test_cr_then_201_CREATED(self):
        testcases = [
            ('/f1/f2/f3/test', True, 'test'),
            ('/f1/f2/f4/f5', True, None),
            ('/f2', False, None),
            ('/test', None, 'test'),
        ]
        for path, p_flag, data in testcases:
            res = self.client.post(self.URL, format='json', data={
                'path': path,
                'data': data,
                'p_flag': p_flag
            })
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_cr_then_400_BAD_REQUEST(self):
        testcases = [
            ('/f1/f2/f3/test', False, 'test'),
            ('/f1/f2/f4/f5', None, None),
        ]
        for path, p_flag, data in testcases:
            data = {
                'path': path,
                'data': data,
                'p_flag': p_flag
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class CatAPITestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:cat')
        repo.create_file(filepath=FilePath('/f1/f2/f3/test'), p_flag=True, data='hello')
        repo.create_file(filepath=FilePath('/f1/f2/f3/f4'), p_flag=True)

    def test_cat_then_200_OK(self):
        res = self.client.post(self.URL, format='json', data={
            'file_path': '/f1/f2/f3/test',
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, {'content': 'hello'})

    def test_cr_then_400_BAD_REQUEST(self):
        testcases = [
            '/f1/f2/f3/abc',
            '/f1'
        ]
        for path in testcases:
            res = self.client.post(self.URL, format='json', data={
                'file_path': path,
            })
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class UpAPITestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:up')
        repo.create_file(filepath=FilePath('/f1/f2/f3/test'), p_flag=True, data='hello')
        repo.create_file(filepath=FilePath('/f1/f2/f3/f4'), p_flag=True)

    def test_up_then_200_OK(self):
        testcases = [
            ('/f1/f2/f3/test', 'hello', 'world'),
            ('/f1/f2/f3/', 'hello', 'world'),
        ]
        for path, name, data in testcases:
            data = {
                'path': path,
                'name': name,
                'data': data,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_up_then_400_BAD_REQUEST(self):
        testcases = [
            ('/f1/f2/f3/test/z', 'hello', 'world'),
            ('/f1/f2/f4/', 'hello', 'world'),
        ]
        for path, name, data in testcases:
            data = {
                'path': path,
                'name': name,
                'data': data,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class MvAPITestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:mv')
        repo.create_file(filepath=FilePath('/f1/f2/f3/test'), p_flag=True, data='hello')
        repo.create_file(filepath=FilePath('/f1/f2/f3/f4'), p_flag=True)

    def test_mv_then_200_OK(self):
        testcases = [
            ('/f1/f2/f3/test', '/f1/f2/'),
            ('/f1/f2/', '/'),
        ]
        for path, folder_path in testcases:
            data = {
                'path': path,
                'folder_path': folder_path,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_mv_then_400_BAD_REQUEST(self):
        testcases = [
            ('/f1/f2/f3/', '/f1/f2/f3/'),
            ('/f1/f2/f3/f4/', '/f1/f2/f3/tes'),
        ]
        for path, folder_path in testcases:
            data = {
                'path': path,
                'folder_path': folder_path,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class RmAPIViewTestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:rm')
        repo.create_file(filepath=FilePath('/f1/f2/f3/test'), p_flag=True, data='hello')
        repo.create_file(filepath=FilePath('/f1/f2/f3/f4'), p_flag=True)

    def test_rm_then_200_OK(self):
        data = {
            'paths': ['/f1/f2/f3/test', '/f1'],
        }
        res = self.client.post(self.URL, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_rm_then_400_BAD_REQUEST(self):
        data = {
            'paths': ['/f1/f2/f3/abc'],
        }
        res = self.client.post(self.URL, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class FindAPIViewTestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:find')
        repo.create_file(filepath=FilePath('/abc/def/agh'), p_flag=True, data='hello')
        repo.create_file(filepath=FilePath('/abc/kkk/jkl/abc'), p_flag=True)

    def test_find_then_200_OK(self):
        testcases = [
            ('/', 'a', [
                '/abc/',
                '/abc/def/agh',
                '/abc/kkk/jkl/abc/',
            ]),
            ('/abc/kkk/jkl/abc', '', ['/abc/kkk/jkl/abc/', ])
        ]
        for folder_path, name, results in testcases:
            data = {
                'folder_path': folder_path,
                'name': name,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data, {'results': results})

    def test_find_then_400_BAD_REQUEST(self):
        testcases = [
            ('/dsf', 'a'),
            ('/abc/kkk/jkl/abc', '')
        ]
        for folder_path, name in testcases:
            data = {
                'paths': folder_path,
                'name': name,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LsAPIViewTestCase(BaseAPITestCase):
    def _setUp(self) -> None:
        self.URL = api_reverse('filesystem:ls')
        repo.create_file(filepath=FilePath('/abc/def/agh'), p_flag=True, data='hello')
        repo.create_file(filepath=FilePath('/abc/kkk/jkl/abc'), p_flag=True)

    def test_ls_then_200_OK(self):
        testcases = [
            ('/', [
                OrderedDict({
                    'name': './',
                    'created_at': str(repo._get_root_directory().created_at).replace('+00:00', 'Z').replace(' ',
                                                                                                            'T'),
                    'updated_at': str(repo._get_root_directory().updated_at).replace('+00:00', 'Z').replace(' ',
                                                                                                            'T'),
                    'size': 5,
                }),
                OrderedDict({
                    'name': 'abc/',
                    'created_at': str(repo.get_file(filepath=FilePath('/abc')).created_at).replace('+00:00',
                                                                                                   'Z').replace(' ',
                                                                                                                'T'),
                    'updated_at': str(repo.get_file(filepath=FilePath('/abc')).updated_at).replace('+00:00',
                                                                                                   'Z').replace(' ',
                                                                                                                'T'),
                    'size': 5,
                }),
            ]),
            ('/', [
                OrderedDict({
                    'name': './',
                    'created_at': str(repo._get_root_directory().created_at).replace('+00:00', 'Z').replace(' ',
                                                                                                            'T'),
                    'updated_at': str(repo._get_root_directory().updated_at).replace('+00:00', 'Z').replace(' ',
                                                                                                            'T'),
                    'size': 5,
                }),
                OrderedDict({
                    'name': 'abc/',
                    'created_at': str(repo.get_file(filepath=FilePath('/abc')).created_at).replace('+00:00',
                                                                                                   'Z').replace(' ',
                                                                                                                'T'),
                    'updated_at': str(repo.get_file(filepath=FilePath('/abc')).updated_at).replace('+00:00',
                                                                                                   'Z').replace(' ',
                                                                                                                'T'),
                    'size': 5,
                }),
            ]),
        ]
        for folder_path, items in testcases:
            data = {
                'folder_path': folder_path,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data, {'items': items})

    def test_ls_then_400_BAD_REQUEST(self):
        testcases = [
            '/dsf',
            '/abc/kkk/jkl/abc'
        ]
        for folder_path in testcases:
            data = {
                'paths': folder_path,
            }
            res = self.client.post(self.URL, data, format='json')
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
