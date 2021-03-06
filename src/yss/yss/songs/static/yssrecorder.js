var karaoke = (function(stream_url, stream_type) {
    var numDisplayLines = 4; // Number of lines to do the karaoke with
    var paused = true;
    var player;
    // cachebust
    rand = Math.random().toString(36).replace(/[^a-z]+/g, '').substr(0, 5);
    if (stream_type.startsWith('audio/') ) {
        player = new Audio();
        player.setAttribute('src', stream_url + '?x=' + rand);
    }
    else {
        player = $('#lyricsvideo')[0];
        var source = $('#lyricsvidsrc')[0];
        source.setAttribute('src', stream_url + '?x=' + rand);
    }
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

    function renderlyrics(when) {
        if (!stream_type.startsWith('audio/')) { return; }
        var st = 0;
        var et = 0;
        $('.yss-karaoke-card').each(function(idx) {
            card = $(this);
            st = parseFloat(card.data('startTime'));
            et = parseFloat(card.data('endTime'));
            if ((st <= when) && (when < et)) {
                card.show();
            }
            else {
                card.hide();
            }
        });
        $('.yss-karaoke-frag').css('color', '#999999');
        $('.yss-karaoke-frag').each(function(idx) {
            st = $(this).data('startTime');
            if (st <= when) {
                $(this).css('color', 'brown');
            }
        });
    }


    function reset() {
        pause();
        player.currentTime = 0;
    }

    function init() {
        renderlyrics(0);
        player.addEventListener('timeupdate', function () {
            var ct = parseFloat(player.currentTime);
            renderlyrics(ct);
            if (ct >= player.duration) {
                reset();
            }
            $('#scrubber')[0].value = ct / player.duration * 100;
            updateStatus();
            lastPosition = ct;
        }, false);

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
        $('#scrubber')[0].onchange = function() {
            player.currentTime = player.duration * (parseFloat(this.value)/100);
        };

    }

    init();
    setup();

    return {
        play: play,
        pause: pause,
        reset: reset,
        playtoggle: playtoggle,
        init: init
    };
});

var rtc_recorder = (function(exports, karaoke, max_framerate, upload_handler) {
    upload_handler = upload_handler||'';
    exports.URL = exports.URL || exports.webkitURL;

    exports.requestAnimationFrame = exports.requestAnimationFrame ||
        exports.webkitRequestAnimationFrame ||
        exports.mozRequestAnimationFrame ||
        exports.msRequestAnimationFrame ||
        exports.oRequestAnimationFrame;

    exports.cancelAnimationFrame = exports.cancelAnimationFrame ||
        exports.webkitCancelAnimationFrame ||
        exports.mozCancelAnimationFrame ||
        exports.msCancelAnimationFrame ||
        exports.oCancelAnimationFrame;

    window.AudioContext = window.AudioContext || window.webkitAudioContext;
    window.URL = window.URL || window.webkitURL;

    var video = $('#camvideo')[0];
    if (video) {
        video.width = 320;
        video.height = 240;
    }
    var audioSelect = $('select#audioSource')[0];
    var videoSelect = $('select#videoSource')[0];
    var rafId = null;
    var startTime = null;
    var endTime = null;
    var audio_context;
    var tagTime = Date.now();
    var recording = false;
    var recorder;
    var thestream;
    var chunks;
    var uploading;

    function displayRecordMode() {
        $('#record-me')[0].innerHTML = '<i class="fas fa-microphone fa-spin"> </i>';
        $('#record-me')[0].onclick = stop;
        $('#record-me').attr('disabled', false);
        $('#play-me').attr('disabled', true);
        $('#play-me')[0].innerHTML = '<i class="fas fa-bullhorn"> </i> Listen';
        $('select#videoSource').attr('disabled', true);
        $('select#audioSource').attr('disabled', true);
        $('.audiocontrol').hide();
    }

    function displayPlayMode() {
        $('#record-me')[0].innerHTML = '<i class="fas fa-microphone"> </i> Record';
        $('#record-me').attr('disabled', false);
        $('#play-me').attr('disabled', false);
        $('#play-me')[0].innerHTML = '<i class="fas fa-bullhorn"> </i> Listen';
        $('select#videoSource').attr('disabled', false);
        $('select#audioSource').attr('disabled', false);
    }

    function gotDevices(deviceInfos) {
        // clear any existing values
        $('select#audioSource option').remove();
        $('select#videoSource option').remove();
        // then add new ones
        selectedVideo = Cookies.get('videodevice');
        selectedAudio = Cookies.get('audiodevice');
        for (var i = 0; i !== deviceInfos.length; ++i) {
            var deviceInfo = deviceInfos[i];
            var option = document.createElement('option');
            option.value = deviceInfo.deviceId;
            if (deviceInfo.kind === 'audioinput' && audioSelect) {
                option.text = deviceInfo.label ||
                    'microphone ' + (audioSelect.length + 1);
                audioSelect.appendChild(option);
                if (option.value == selectedAudio) {
                    option.selected = true;
                }
            } else if (deviceInfo.kind === 'videoinput' && videoSelect) {
                option.text = deviceInfo.label || 'camera ' +
                    (videoSelect.length + 1);
                videoSelect.appendChild(option);
                if (option.value == selectedVideo) {
                    option.selected = true;
                }
            }
        }
        if (videoSelect) {
            nocam_option = document.createElement('option');
            nocam_option.value = '';
            nocam_option.text = 'No Camera';
            if (selectedVideo === '') {
                nocam_option.selected = true;
            }
            videoSelect.appendChild(nocam_option);
        }
    }


    function getStream() {
        if (thestream) {
            thestream.getTracks().forEach(function(track) {
                track.stop();
            });
        }
        var constraints = {
            "audio": {
                "deviceId": {exact: audioSelect.value}
            },
        };
        if (videoSelect && videoSelect.value != '') {
            vidconstraint = {
                "width": { exact: "320" },
                "height": { exact: "240"},
                "frameRate": { min: 5, max: max_framerate },
                "deviceId": { exact: videoSelect.value}
            };
            constraints.video = vidconstraint;
        }
        navigator.mediaDevices.getUserMedia(constraints).then(gotStream);
    }

    function gotStream(stream) {
        thestream = stream;
        if (video) {
            video.srcObject = stream;
            video.controls = false;
        }
        recorder = new MediaRecorder(stream, {
            mimeType: "video/webm;codecs=vp8,opus" // works in FF and chrome
        });

        audio_context = new AudioContext();

        var micinput = audio_context.createMediaStreamSource(stream);

        // mic level (control disabled for now)
        modulatorInput = audio_context.createGain();
        modulatorGain = audio_context.createGain();
        modulatorGain.gain.value = 1.0;
        modulatorGain.connect( modulatorInput );
        micinput.connect(modulatorGain);
        $('#micLevel')[0].onchange = function() {
            modulatorGain.gain.value = parseFloat(this.value);
        };

        // fbo mic volume meter
        analyser = audio_context.createAnalyser();
        scriptprocessor = audio_context.createScriptProcessor(2048, 1, 1);
        analyser.smoothingTimeConstant = 0.8;
        analyser.fftSize = 1024;
        micinput.connect(analyser);
        scriptprocessor.connect(audio_context.destination);

        function colorPids(vol) {
            var all_pids = $('.mic-vol-block');
            var amout_of_pids = Math.round(vol/10);
            var elem_range = all_pids.slice(0, amout_of_pids);
            for (var i = 0; i < all_pids.length; i++) {
                all_pids[i].style.backgroundColor="#e6e7e8";
            }
            for (var j = 0; j < elem_range.length; j++) {
                elem_range[j].style.backgroundColor="#69ce2b";
            }
        }

        scriptprocessor.onaudioprocess = function() {
            var array = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(array);
            var values = 0;

            var length = array.length;
            for (var i = 0; i < length; i++) {
                values += (array[i]);
            }
            var average = values / length;

            //console.log(Math.round(average));
            colorPids(average);
        };

        var finishVideoSetup_ = function() {
            // Note: video.onloadedmetadata doesn't fire in Chrome when using
            // getUserMedia so we have to use setTimeout. See crbug.com/110938.
            setTimeout(function() {
                video.width = 320;//video.clientWidth;
                video.height = 240;// video.clientHeight;
            }, 1000);
        };

        if (video) {
            finishVideoSetup_();
        }
    }

    function record() {
        if (recorder === undefined) { return; }

        karaoke.reset();
        karaoke.play();
        displayRecordMode();
        recording = true;
        startTime = Date.now();

        chunks = [];
        recorder.addEventListener('dataavailable', function(e) {
            if (e.data.size > 0) {
                chunks.push(e.data);
            }
        });
        recorder.addEventListener('stop', function(e) {
            // dataavailable is guaranteed to have been called by this point
            if (!uploading) {
                gatherMetadata();
            }
        });
        recorder.start();
    }

    function stop() {
        thestream.getTracks().forEach(function(track) {
            track.stop();
        });
        if (recorder === undefined) { return; }
        displayPlayMode();
        karaoke.pause();
        recording = false;
        endTime = Date.now();
        if (recorder.state != 'inactive') {
            recorder.stop();
        }
    }

    function abandon() {
        $('#metadata-overlay')[0].style.display = "none";
        $('#uploading-overlay')[0].style.display = "none";
        $(document).off("keyup");
        init();  // reload stream
    }

    function gatherMetadata() {
        if (!$('#metadata-overlay').length) {
            /// empty
            return uploadVideo();
        }
        $('#metadata-overlay')[0].style.display = "block";
        $('#uploading-overlay')[0].style.display = "none";
        $('#upload-me')[0].onclick = uploadVideo;
        $('#cancel-me')[0].onclick = abandon;
        $(document).keyup(function(e) {
           if (e.keyCode === 27) abandon();   // esc
        });
    }

    function uploadVideo() {
        if ($('#metadata-overlay').length) {
            $('#metadata-overlay')[0].style.display = "none";
        }
        $('#uploading-overlay')[0].style.display = "block";
        uploading = true;
        var blob = new Blob(chunks);
        chunks = [];
        var fd = new FormData();
        effects = $('.effects');
        for (var i = 0; i < effects.length; i++) {
            effect = effects[i];
            if (effect.checked) {
                fd.append('effects', effect.id);
            }
        }
        if ($('#voladjust').length) {
            fd.append('voladjust', $('#voladjust')[0].value);
        }
        fd.append('data', blob);
        fd.append('finished', '1');
        url = upload_handler || window.location;
        jQuery.ajax({
            xhr: function() {
                var xhr = new window.XMLHttpRequest();
                xhr.upload.addEventListener("progress", function(evt) {
                    if (evt.lengthComputable && $('#upload-progress')) {
                        var percentComplete = evt.loaded / evt.total;
                        fmt = Math.round(percentComplete*100);
                        $('#upload-progress').text(fmt + '%');
                        $('#upload-progress').attr('aria-valuenow',
                                                   (percentComplete*100));
                        $('#upload-progress').attr(
                            'style',
                            'width: ' + fmt +'%; min-width: 1em;'
                        );
                    }
                }, false);
                return xhr;
            },
            type:'POST',
            url: url,
            data: fd,
            processData: false,
            contentType: false,
        }).done(function(data) { window.location = data; });

    }

    function initEvents() {
        $('#record-me')[0].onclick = record;
        $('#play-me')[0].onclick = karaoke.playtoggle;
    }

    function setAudioAndGetStream() {
        Cookies.set('audiodevice', this.value);
        return getStream();
    }

    function setVideoAndGetStream() {
        Cookies.set('videodevice', this.value);
        return getStream();
    }

    function init() {
        navigator.mediaDevices.enumerateDevices().then(gotDevices).then(
            getStream);
        if (audioSelect) {
            audioSelect.onchange = setAudioAndGetStream;
        }
        if (videoSelect) {
            videoSelect.onchange = setVideoAndGetStream;
        }
        initEvents();
    }

    init();

    return {
        stop: stop,
    };

});
