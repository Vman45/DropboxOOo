#!
# -*- coding: utf_8 -*-

import uno
import unohelper

from com.sun.star.ucb.ConnectionMode import OFFLINE
from com.sun.star.ucb.ConnectionMode import ONLINE
from com.sun.star.auth.RestRequestTokenType import TOKEN_NONE
from com.sun.star.auth.RestRequestTokenType import TOKEN_URL
from com.sun.star.auth.RestRequestTokenType import TOKEN_REDIRECT
from com.sun.star.auth.RestRequestTokenType import TOKEN_QUERY
from com.sun.star.auth.RestRequestTokenType import TOKEN_JSON
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_RETRIEVED
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_CREATED
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_FOLDER
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_FILE
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_RENAMED
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_REWRITED
from com.sun.star.ucb.RestDataSourceSyncMode import SYNC_TRASHED

from dropbox import ProviderBase
from dropbox import g_identifier
from dropbox import g_provider
from dropbox import g_host
from dropbox import g_url
from dropbox import g_upload
from dropbox import g_userfields
from dropbox import g_drivefields
from dropbox import g_itemfields
from dropbox import g_chunk
from dropbox import g_buffer
from dropbox import g_folder
from dropbox import g_office
from dropbox import g_link
from dropbox import g_doc_map

# pythonloader looks for a static g_ImplementationHelper variable
g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationName = '%s.Provider' % g_identifier


class Provider(ProviderBase):
    def __init__(self, ctx):
        self.ctx = ctx
        self.Scheme = ''
        self.Plugin = ''
        self.Link = ''
        self.Folder = ''
        self.SourceURL = ''
        self.SessionMode = OFFLINE
        self._Error = ''

    @property
    def Name(self):
        return g_provider
    @property
    def Host(self):
        return g_host
    @property
    def BaseUrl(self):
        return g_url
    @property
    def UploadUrl(self):
        return g_upload
    @property
    def Office(self):
        return g_office
    @property
    def Document(self):
        return g_doc_map
    @property
    def Chunk(self):
        return g_chunk
    @property
    def Buffer(self):
        return g_buffer

    @property
    def FileSyncModes(self):
        return (SYNC_CREATED, SYNC_REWRITED)

    def getRequestParameter(self, method, data=None):
        parameter = uno.createUnoStruct('com.sun.star.auth.RestRequestParameter')
        parameter.Name = method
        if method == 'getUser':
            parameter.Method = 'POST'
            parameter.Url = '%s/users/get_current_account' % self.BaseUrl
        elif method == 'getItem':
            parameter.Method = 'POST'
            parameter.Url = '%s/file_requests/get' % self.BaseUrl
            parameter.Data = '{"id": "%s"}' % data.getValue('Id')
        elif method == 'getFolderContent':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/list_folder' % self.BaseUrl
            path = '' if data.getValue('IsRoot') else data.getValue('Id')
            parameter.Json = '{"path": "%s", "include_deleted": false}' % path
            token = uno.createUnoStruct('com.sun.star.auth.RestRequestToken')
            token.Type = TOKEN_URL | TOKEN_JSON
            token.Field = 'cursor'
            token.Value = '%s/files/list_folder/continue' % self.BaseUrl
            token.IsConditional = True
            token.ConditionField = 'has_more'
            token.ConditionValue = True
            enumerator = uno.createUnoStruct('com.sun.star.auth.RestRequestEnumerator')
            enumerator.Field = 'entries'
            enumerator.Token = token
            parameter.Enumerator = enumerator
        elif method == 'getDocumentContent':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/download' % self.UploadUrl
            path = '{\\"path\\": \\"%s\\"}' % data.getValue('Id')
            parameter.Header = '{"Dropbox-API-Arg": "%s"}' % path
        elif method == 'updateTitle':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/move_v2' % self.BaseUrl
            path = '' if data.getValue('AtRoot') else data.getValue('ParentId')
            path += '/%s' % data.getValue('Title')
            parameter.Json = '{"from_path": "%s","to_path": "%s"}' % (data.getValue('Id'), path)
        elif method == 'updateTrashed':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/delete_v2' % self.BaseUrl
            parameter.Json = '{"path": "%s"}' % data.getValue('Id')
        elif method == 'createNewFolder':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/create_folder_v2' % self.BaseUrl
            path = '' if data.getValue('AtRoot') else data.getValue('ParentId')
            path += '/%s' % data.getValue('Title')
            parameter.Json = '{"path": "%s"}' % path
        elif method == 'createNewFile':
            parameter.Method = 'POST'
            parameter.Url = '%s/file_requests/create' % self.BaseUrl
            title = data.getValue('Title')
            path = '/' if data.getValue('AtRoot') else data.getValue('ParentId')
            path += '/%s' % title
            parameter.Json = '{"title": "%s", "destination": "%s"}' % (title, path)
        elif method == 'getUploadLocation':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/get_temporary_upload_link' % self.BaseUrl
            path = '"path": "%s"' % data.getValue('Id')
            mode = '"mode": "overwrite"'
            mute = '"mute": true'
            info = '{"commit_info": {%s, %s, %s}}' % (path, mode, mute)
            parameter.Json = info
        elif method == 'getNewUploadLocation':
            parameter.Method = 'POST'
            parameter.Url = '%s/files/get_temporary_upload_link' % self.BaseUrl
            path = '' if data.getValue('AtRoot') else data.getValue('ParentId')
            path += '/%s' % data.getValue('Title')
            path = '"path": "%s"' % path
            mode = '"mode": "add"'
            mute = '"mute": true'
            info = '{"commit_info": {%s, %s, %s}}' % (path, mode, mute)
            parameter.Json = info
        elif method == 'getUploadStream':
            parameter.Method = 'POST'
            parameter.Url = data.getValue('link')
            parameter.Header = '{"Content-Type": "application/octet-stream"}'
        return parameter

    def getUserId(self, user):
        return user.getValue('account_id')
    def getUserName(self, user):
        return user.getValue('email')
    def getUserDisplayName(self, user):
        return user.getValue('name').getValue('display_name')

    def getItemParent(self, item, rootid):
        ref = item.getDefaultValue('parentReference', self._getKeyMap())
        parent = ref.getDefaultValue('id', rootid)
        return (parent, )

    def getRootId(self, item):
        return self.getItemId(item)
    def getRootTitle(self, item):
        return self.getItemTitle(item)
    def getRootCreated(self, item, timestamp=None):
        return timestamp
    def getRootModified(self, item, timestamp=None):
        return timestamp
    def getRootMediaType(self, item):
        return self.Folder
    def getRootSize(self, item):
        return 0
    def getRootTrashed(self, item):
        return False
    def getRootCanAddChild(self, item):
        return True
    def getRootCanRename(self, item):
        return False
    def getRootIsReadOnly(self, item):
        return False
    def getRootIsVersionable(self, item):
        return False

    def getItemId(self, item):
        return item.getDefaultValue('id', None)
    def getItemTitle(self, item):
        return item.getDefaultValue('name', None)
    def getItemCreated(self, item, timestamp=None):
        created = item.getDefaultValue('server_modified', None)
        if created:
            return self.parseDateTime(created, '%Y-%m-%dT%H:%M:%SZ')
        return timestamp
    def getItemModified(self, item, timestamp=None):
        modified = item.getDefaultValue('client_modified', None)
        if modified:
            return self.parseDateTime(modified, '%Y-%m-%dT%H:%M:%SZ')
        return timestamp
    def getItemMediaType(self, item):
        tag = item.getDefaultValue('.tag', 'folder')
        return 'application/octet-stream' if tag != 'folder' else self.Folder
    def getItemSize(self, item):
        return int(item.getDefaultValue('size', 0))
    def getItemTrashed(self, item):
        return item.getDefaultValue('trashed', False)
    def getItemCanAddChild(self, item):
        return True
    def getItemCanRename(self, item):
        return True
    def getItemIsReadOnly(self, item):
        return False
    def getItemIsVersionable(self, item):
        return False

    def getResponseId(self, response, default):
        id = response.getDefaultValue('metadata', self._getKeyMap()).getDefaultValue('id', None)
        if id is None:
            id = default
        return id
    def getResponseTitle(self, response, default):
        title = response.getDefaultValue('metadata', self._getKeyMap()).getDefaultValue('name', None)
        if title is None:
            title = default
        return title

    def getRoot(self, request, user):
        id = user.getValue('root_info').getValue('root_namespace_id')
        root = self._getKeyMap()
        root.insertValue('id', id)
        root.insertValue('name', 'Homework')
        response = uno.createUnoStruct('com.sun.star.beans.Optional<com.sun.star.auth.XRestKeyMap>')
        response.IsPresent = True
        response.Value = root
        return response

    def createFile(self, uploader, item):
        parameter = self.getRequestParameter('createNewFile', item)
        return self.Request.execute(parameter)

    # XServiceInfo
    def supportsService(self, service):
        return g_ImplementationHelper.supportsService(g_ImplementationName, service)
    def getImplementationName(self):
        return g_ImplementationName
    def getSupportedServiceNames(self):
        return g_ImplementationHelper.getSupportedServiceNames(g_ImplementationName)


g_ImplementationHelper.addImplementation(Provider,
                                         g_ImplementationName,
                                        (g_ImplementationName, ))
