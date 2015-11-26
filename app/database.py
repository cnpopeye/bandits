#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime


def logtime(dbname):
    def _logtime(func):
        def __logtime(*args, **keywords):
            result = func(*args, **keywords)
            if result:
                update_col = {}
                update_col[dbname+'_updated_at'] = datetime.utcnow()
                res_ope = mongo.db.game_config.update({}, {'$set': update_col}, w=1)
                if not res_ope.get('err') and res_ope.get('n') == 1:
                    return result
                else:
                    return False                
            return result
        return __logtime
    return _logtime

def mlogtime():
    def _mlogtime(func):
        def __mlogtime(*args, **keywords):
            result = func(*args, **keywords)
            if result:
                update_col = {}
                update_col[args[0].name+'_updated_at'] = datetime.utcnow()
                res_ope = mongo.db.game_config.update({}, {'$set': update_col}, w=1)
                if not res_ope.get('err') and res_ope.get('n') == 1:
                    return result
                else:
                    return False                
            return result
        return __mlogtime
    return _mlogtime



class Manager:
    def __init__(self, name, mongo):
        self.mongo = mongo
        self.data = self.mongo.db[name]
        self.name = name
        self.id = self.name + '_id'

    def exists(self, docId):
        doc = self.data.find_one({self.id: docId})
        return doc is None
    
    def is_id_used(self, docId):
        doc = self.data.find_one({'id': docId})
        return doc    
    
    @mlogtime()    
    def add(self, doc):
        doc[self.id] = self._new_id()
        doc['created_at'] = datetime.utcnow()
        doc['updated_at'] = datetime.utcnow()
        return self.data.insert(doc, w=1)

    def get_by_id(self, docId):
        return self.data.find_one({self.id: docId})

    def get_by_page(self, spec=None, pagenum=1, pagesize=1000):
        skip = (pagenum - 1) * pagesize
        docs = self.data.find(  skip=skip, sort=[('id', 1)], limit=pagesize)
        docs_count = docs.count()
        pagecount = docs_count // pagesize
        if docs_count % pagesize > 0:
            pagecount += 1
        return pagecount, docs

    def _new_id(self):
        docs = self.data.find({}, {"_id":0, self.id:1}).sort([(self.id,-1)]).limit(1)
        return (int(docs[0][self.id]) + 1) if docs.count() > 0 else 1

    @mlogtime()
    def delete_by_ids(self, ids):
        res_rem = self.data.remove({self.id: {'$in': ids}}, w=1)
        return (not res_rem.get('err') and res_rem.get('n') == len(ids))

    @mlogtime()
    def update(self, doc):
        doc['updated_at'] = datetime.utcnow()
        res_rem = self.data.update({self.id: doc[self.id]}, {'$set': doc}, w=1)
        return (not res_rem.get('err') and res_rem.get('n') == 1)


    def get_all_id_name(self):
            cursor = self.data.find({}, {'_id': 0,'id': 1,'name': 1})
            dict = {e['id']: e['name'] for e in cursor}
            return dict    

