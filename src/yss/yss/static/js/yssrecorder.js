var karaoke = (function(mp3_url, timings) {
    var numDisplayLines = 4; // Number of lines to do the karaoke with
    var paused = true;
    var show = null;
    var player = new Audio();
    player.setAttribute('src', mp3_url);
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
        show.reset();
        player.play();
        paused = false;
        var b = $('#play-me')[0];
        b.innerHTML = '<i class="glyphicon glyphicon-pause"> </i> Pause';
    }

    function pause() {
        show.reset();
        player.pause();
        paused = true;
        var b = $('#play-me')[0];
        b.innerHTML = '<i class="glyphicon glyphicon-play"> </i> Play ';
    }

    function playtoggle() {
        if (paused) {
            play();
        }
        else {
            pause();
        }
    }

    function reset() {
        pause();
        player.currentTime = 0;
    }

    function init() {
        // Create the karaoke engine and get a show instance
        var rice = new RiceKaraoke(RiceKaraoke.simpleTimingToTiming(timings));
        var renderer = new SimpleKaraokeDisplayEngine(
            'karaoke-display', numDisplayLines);
        show = rice.createShow(renderer, numDisplayLines);

        player.addEventListener(
            'error', function(e) { alert('Failed to play! ' + e); }, false);
        player.addEventListener('ended', function() {
            reset();
        }, false);
        player.addEventListener('timeupdate', function () {
            var ct = player.currentTime;
            if (ct < lastPosition) {
                show.reset();
            }
            if (ct >= player.duration) {
                reset();
            }
            show.render(ct, false);
            updateStatus();
            lastPosition = ct;
        }, false);
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

var rtc_recorder = (function(exports, karaoke, max_framerate) {
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

    var video = $('video')[0];
    var audioSelect = $('select#audioSource')[0];
    var videoSelect = $('select#videoSource')[0];
    video.width = 320;
    video.height = 240;
    var rafId = null;
    var startTime = null;
    var endTime = null;
    var audio_context;
    var tagTime = Date.now();
    var recording = false;
    var recorder;
    var thestream;
    var chunks;

    function toggleActivateRecordButton() {
        var b = $('#record-me')[0];
        b.classList.toggle('recording');
        b.disabled = !b.disabled;
    }

    function gotDevices(deviceInfos) {
        for (var i = 0; i !== deviceInfos.length; ++i) {
            var deviceInfo = deviceInfos[i];
            var option = document.createElement('option');
            option.value = deviceInfo.deviceId;
            if (deviceInfo.kind === 'audioinput') {
                option.text = deviceInfo.label ||
                    'microphone ' + (audioSelect.length + 1);
                audioSelect.appendChild(option);
            } else if (deviceInfo.kind === 'videoinput') {
                option.text = deviceInfo.label || 'camera ' +
                    (videoSelect.length + 1);
                videoSelect.appendChild(option);
            }
        }
        nocam_option = document.createElement('option');
        nocam_option.value = '';
        nocam_option.text = 'No Camera';
        videoSelect.appendChild(nocam_option);
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
        if (videoSelect.value != '') {
            vidconstraint = {
                "width": { exact: "640" },
                "height": { exact: "480"},
                "frameRate": { min: 5, max: max_framerate },
                "deviceId": { exact: videoSelect.value}
            };
            constraints.video = vidconstraint;
        }
        navigator.mediaDevices.getUserMedia(constraints).then(gotStream);
    }

    function gotStream(stream) {
        thestream = stream;
        video.srcObject = stream;
        video.controls = false;
        recorder = new MediaRecorder(stream, {
            mimeType: "video/webm;codecs=vp8,opus" // works in FF and chrome
        });

        audio_context = new AudioContext();

        var micinput = audio_context.createMediaStreamSource(stream);

        // mic level
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

        finishVideoSetup_();
    }

    function record() {
        if (recorder === undefined) { return; }

        karaoke.reset();
        karaoke.play();
        recording = true;
        startTime = Date.now();

        toggleActivateRecordButton();
        $('select#audioSource')[0].disabled = true;
        $('select#videoSource')[0].disabled = true;
        $('#stop-me')[0].disabled = false;
        $('#play-me')[0].disabled = true;

        chunks = [];
        recorder.addEventListener('dataavailable', function(e) {
            if (e.data.size > 0) {
                chunks.push(e.data);
            }
        });
        recorder.addEventListener('stop', function(e) {
            // dataavailable is guaranteed to have been called by this point
            uploadVideo();
        });
        recorder.start();
    }

    function stop() {
        thestream.getTracks().forEach(function(track) {
            track.stop();
        });
        if (recorder === undefined) { return; }
        karaoke.pause();
        recording = false;
        endTime = Date.now();
        $('#stop-me')[0].disabled = true;
        $('#play-me')[0].disabled = false;
        $('select#audioSource')[0].disabled = false;
        $('select#videoSource')[0].disabled = false;
        $('#uploading-overlay')[0].style.display = "block";
        toggleActivateRecordButton();
        recorder.stop();
    }

    function uploadVideo() {
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
        fd.append('musicvolume', $('#musicvolume')[0].value);
        fd.append('data', blob);
        fd.append('finished', '1');
        jQuery.ajax({
            type:'POST',
            url: window.location,
            data: fd,
            processData: false,
            contentType: false
        }).done(function(data) { window.location = data; });

    }

    function initEvents() {
        $('#record-me')[0].addEventListener('click', record);
        $('#stop-me')[0].addEventListener('click', stop);
        $('#play-me')[0].addEventListener('click', karaoke.playtoggle);
    }

    navigator.mediaDevices.enumerateDevices().then(gotDevices).then(getStream);
    audioSelect.onchange = getStream;
    videoSelect.onchange = getStream;
    initEvents();

    return {
        stop: stop,
    };

});
