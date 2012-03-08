import json
import uuid
import couchdb
import time

class Dao(object):
    '''the dao that can be named is not the true dao'''
    __type__ = None

    def __init(self, **kwargs):
        self.couch, self.db = self.connection()
        self._data = dict(kwargs)
        self._id = self.data.get('_id',None)
        self._version = self.data.get('_rev',None)

    @classmethod
    def connection(cls):
        # read these from config
        couch_url = 'http://localhost:5984/'
        couch_db = 'ti'
        
        couch = couchdb.Server(url=couch_url)
        db = couch[couch_db]
        return couch, db

    @property
    def data(self):
        return self._data
        
    @data.setter
    def data(self, val):
        self._data = val

    @property
    def id(self):
        return self._id
    
    @id.setter
    def id(self,_id):
        self._id = _id
        
    @property
    def version(self):
        return self._version
        
    @property
    def json(self):
        return json.dumps(self.data,sort_keys=True,indent=4)

    @classmethod
    def get(cls,_id):
        couch, db = cls.connection()
        try:
            return cls(**db[_id])
        except:
            return None

    def query(self,**kwargs):
        # pass queries through to couchdb, as per couchdb-python query
        # http://packages.python.org/CouchDB/client.html
        return self.db.query(**kwargs)
        
    def view(self, viewname):
        return self.db.view(viewname)
        
    def save(self):
        if '_id' not in self.data:
            if self.id:
                self.data['_id'] = self.id            
            else:
                self.data['_id'] = uuid.uuid4().hex
                self.id = self.data['_id']
        if '_rev' not in self.data and self.version:
            self.data['_rev'] = self.version
            
        if 'created' not in self.data:
            self.data['created'] = time.time()
            
        self.data['last_modified'] = time.time()

        try:
            self._id, self._version = self.db.save(self.data)
            self.data['_rev'] = self.version
            return self.id
        except:
            # log the save error? action on doc update conflict?
            return False
        
    def delete(self):
        try:
            self.data = {}
            self.db.delete(self.data)
            return True
        except:
            # log the delete error? action on doc update conflict?
            return False


