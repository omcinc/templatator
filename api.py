import json

import falcon

from tttor.tttor import expand_all


class ExpandAll:
    def on_get(self, req, resp, save_draft):
        print("save_draft=%s" % save_draft)
        result = expand_all()
        resp.body = json.dumps(result)


api = falcon.API()
api.add_route('/expand', ExpandAll())
