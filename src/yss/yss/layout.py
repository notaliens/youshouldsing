from pyramid_layout.layout import layout_config


@layout_config(template="templates/main_layout.pt")
class MainLayout(object):
    page_title = "You should sing!"

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def static(self, path):
        return self.request.static_url("yss:static/" + path)
