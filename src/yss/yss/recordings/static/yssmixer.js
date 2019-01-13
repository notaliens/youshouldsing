var yssmixer = (function(stream_url, submit_handler) {
    var numDisplayLines = 4; // Number of lines to do the karaoke with
    var paused = true;
    var show = null;
    var player = new Audio();
    // cachebust
    rand = Math.random().toString(36).replace(/[^a-z]+/g, '').substr(0, 5);
    player.setAttribute('src', stream_url + '?x=' + rand);
    var lastPosition = 0;

    function getTimeString(t) {
        var min = Math.floor(t / 60);
        var secs = Math.floor(t % 60);
        return min + ':' + (secs < 10 ? '0' : '') + secs;
    }

    function changePosition(percent) {
        if (player != null) {
            var duration = player.duration;
            var position = duration * percent / 100;
            player.currentTime = position;
        }
    }

    function updateStatus() {
        var duration = player.duration;
        $('#status').text(getTimeString(player.currentTime) + ' / ' +
                          getTimeString(duration));
    }

    function setup() {
        $('#player').show();
    }

    function play() {
        $('.audiocontrol').show();
        player.play();
        paused = false;
    }

    function pause() {
        player.pause();
        $('.audiocontrol').hide();
        paused = true;
    }

    function playtoggle() {
        var b = $('#play-me')[0];
        if (paused) {
            play();
            b.innerHTML = '<i class="fas fa-bullhorn fa-spin"> </i>';
        }
        else {
            pause();
            b.innerHTML = '<i class="fas fa-bullhorn"> </i> Listen';
        }
    }

    function reset() {
        pause();
        player.currentTime = 0;
    }

    function uploadForm() {
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
        url = submit_handler || window.location;
        jQuery.ajax({
            type:'POST',
            url: url,
            data: fd,
            processData: false,
            contentType: false,
        }).done(function(data) { window.location = data; });
    }

    function init() {
        $('#forward')[0].onclick = function() {
            player.currentTime = player.currentTime + 5;
        };

        $('#reverse')[0].onclick = function() {
            back = player.currentTime - 5;
            if (back < 0) {
                player.currentTime = 0;
            }
            else {
                player.currentTime = back;
            }
        };

        player.addEventListener(
            'error', function(e) { alert('Failed to play! ' + e); }, false);
        player.addEventListener('ended', function() {
            $('#play-me')[0].innerHTML = '<i class="fas fa-bullhorn"> </i> Listen';
            player.currentTime = 0;
            $('.audiocontrol').hide();
            reset();
        }, false);

        $('#remix-me')[0].onclick = uploadForm;
        $('#play-me')[0].onclick = playtoggle;
        $('#latency').change(function() {
            $('#latencydisplay')[0].innerHTML = this.value;
        });
    }

    init();
    setup();

    return {
        play: play,
        pause: pause,
        reset: reset,
        playtoggle: playtoggle
    };
});
