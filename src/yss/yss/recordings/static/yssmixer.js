var yssmixer = (function(stream_url, remix_handler, acc_handler, rej_handler,
                         progress_url, ismixed) {
    var paused = true;
    var show = null;
    var player = $('#player');
    var mixprogress = $('#mixprogress');
    var overlay = $('#remixing-overlay');

    // cachebust
    rand = Math.random().toString(36).replace(/[^a-z]+/g, '').substr(0, 5);
    player[0].setAttribute('src', stream_url + '?x=' + rand);
    var last_played_time = 0;

    function progresscheck() {
        console.log('progress check using url ' + progress_url);
        $.ajax(
            {"url":progress_url,
             "success": function(data) {
                 console.log(data);
                 if (data.done) {
                     rand = Math.random().toString(
                         36).replace(/[^a-z]+/g, '').substr(0, 5);
                     last_played_time = player[0].currentTime;
                     console.log('resetting video');
                     player[0].setAttribute(
                         'src', stream_url + "?x=" + rand); // cachebust
                     player.load();
                     player.show();
                     player[0].play();
                     overlay.hide();
                 }
                 else {
                     mixprogress.text(data.status);
                     mixprogress.attr('aria-valuenow', data.pct);
                     mixprogress.attr(
                         'style',
                         'width: ' + data.pct +'%; min-width: 10em;'
                     );
                     if (data.pct != -1) {
                         // if it's not in a terminal failure state,
                         // do it again
                         setTimeout(progresscheck, 1000); //every second
                     }
                 }
             }
            });
    }

    function remix() {
        console.log('uploading form data');
        overlay.show();
        var fd = new FormData();
        effects = $('.effects');
        for (var i = 0; i < effects.length; i++) {
            effect = effects[i];
            if (effect.checked) {
                fd.append('effects', effect.id);
            }
        }
        if ($('#voladjust')[0]) {
            fd.append('voladjust', $('#voladjust')[0].value);
        }
        if ($('#show-camera')[0]) {
            fd.append('show-camera', $('#show-camera')[0].checked);
        }
        if ($('#latency')[0]) {
            fd.append('latency', $('#latency')[0].value);
        }

        jQuery.ajax({
            type:'POST',
            url: remix_handler,
            data: fd,
            processData: false,
            contentType: false,
        }).done(function(needs_remixing) {
            if (needs_remixing) {
                // if it returns false, no actual changes were made to
                // values that would effect the mixing state
                console.log('needs remixing');
                setTimeout(progresscheck, 0);
            }
            else {
                overlay.hide();
            }
        });
    }

    function accept() {
        var visibility = $("input[name='visibility']:checked")[0].value;
        var description = $('#description')[0].value;
        var fd = new FormData();
        fd.append('description', description);
        fd.append('visibility', visibility);
        jQuery.ajax({
            type: 'POST',
            url: acc_handler,
            data: fd,
            processData: false,
            contentType: false,
        }).done(function(url) {
            window.location = url;
        });
    }

    function reject() {
        if (confirm('If you throw this recording away, you will not be able ' +
                    'to get it back.  Are you sure?')) {
            jQuery.ajax({
                type:'POST',
                url: rej_handler,
            }).done(function(url) {
                window.location = url;
            });
        }
    }

    function init() {
        if (!ismixed) { // first-time mix, let performer throw out recording
            $('#reject').show();
        }
        player[0].addEventListener('error', function(e) {
            alert('Failed to play! ' + e);
        }, false);
        player[0].addEventListener('ended', function() {
            player[0].currentTime = 0;
        }, false);
        player[0].addEventListener('loadedmetadata', function() {
            player[0].currentTime = last_played_time;
        }, false);
        $('#reject').click(reject);
        $('#accept').click(accept);
        $('.knob').change(remix);
        $('#latency').change(function() {
            $('#latencydisplay')[0].innerHTML = this.value;
        });
    }

    init();

    return {
        progresscheck: progresscheck
    };
});
