var liker = (function(like_url, unlike_url, like_button_id, unlike_button_id,
                      like_count_id) {
    like_url = like_url || '@@like';
    unlike_url = unlike_url || '@@unlike';
    like_button_id = like_button_id || '#like-button';
    unlike_button_id = unlike_button_id || '#unlike-button';
    like_count_id = like_count_id || '#like-count';
    
    $(like_button_id).click(function () {
        $.ajax(like_url)
            .success(function(data) {
                var message;
                if (data.num_likes == 1) {
                    message = data.num_likes + ' performer has liked';
                }
                else {
                    message = data.num_likes + ' performers have liked';
                }
                
                $(like_count_id).text(message);
                $(like_button_id).hide();
                $(unlike_button_id).show();
            }).fail(function() {
                alert('Failed to add like');
            });
        return false;
    });


    $(unlike_button_id).click(function () {
        $.ajax(unlike_url)
            .success(function(data) {
                var message;
                if (data.num_likes == 1) {
                    message = data.num_likes + ' performer has liked';
                }
                else {
                    message = data.num_likes + ' performers have liked';
                }
                
                $(like_count_id).text(message);
                $(unlike_button_id).hide();
                if (data.can_like) {
                    $(like_button_id).show();
                }
            }).fail(function() {
                alert('Failed to unlike');
            });
        return false;
    });
});

