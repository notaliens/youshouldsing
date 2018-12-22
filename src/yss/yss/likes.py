def has_liked(request, resource):
    user = request.user
    if user is not None:
        performer = user.performer
        if performer is not None:
            return performer in resource.liked_by
            
def can_like(request, resource):
    if not has_liked(request, resource):
        return request.has_permission('yss.like', resource)
    
