var karaoke = (function(mp3_url, timings, recording_id) {
    var numDisplayLines = 4; // Number of lines to do the karaoke with
    var timings = timings;
    var wasPaused = false;
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
        player.play();
    }

    function pause() {
        player.pause();
    }

    function init() {
        // Create the karaoke engine and get a show instance
        var rice = new RiceKaraoke(RiceKaraoke.simpleTimingToTiming(timings));
        var renderer = new SimpleKaraokeDisplayEngine(
            'karaoke-display', numDisplayLines);
        show = rice.createShow(renderer, numDisplayLines);

        player.addEventListener(
            'error', function(e) { alert('Failed to play! ' + e) }, false);
        player.addEventListener('ended', function() {
            // AFAICT this isn't called
            player.pause();
            rtc_recorder.stop();
        }, false);
        player.addEventListener('timeupdate', function () {
            var ct = player.currentTime;
            if (ct < lastPosition) {
                show.reset();
            }
            if (ct >= player.duration) {
                rtc_recorder.stop();
            }
            show.render(ct, false);
            updateStatus();
            lastPosition = ct;
        }, false);
    };

    init();
    setup();

    return {
        play: play,
    }
});

var rtc_recorder = (function(exports, karaoke, recording_id, framerate) {
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

    var CANVAS_WIDTH = 320;
    var CANVAS_HEIGHT = 240;
    const video = $('video')[0];
    const audioSelect = $('select#audioSource')[0];
    const videoSelect = $('select#videoSource')[0];
    video.width = CANVAS_WIDTH;
    video.height = CANVAS_HEIGHT;
    var canvas = document.createElement('canvas'); // offscreen canvas.
    canvas.width = CANVAS_WIDTH;
    canvas.height = CANVAS_HEIGHT;
    var rafId = null;
    var startTime = null;
    var endTime = null;
    var audio_context;
    var recorder;
    var tagTime = Date.now();
    var recording = false;
    var framerate = framerate;
    var video_frames;

    function toggleActivateRecordButton() {
        var b = $('#record-me')[0];
        b.textContent = b.disabled ? 'Record' : 'Recording...';
        b.classList.toggle('recording');
        b.disabled = !b.disabled;
    }

    function getStream() {
        if (window.stream) {
            window.stream.getTracks().forEach(function(track) {
                track.stop();
            });
        }
        const constraints = {
            "audio": {
                "deviceId": {exact: audioSelect.value}
            },
            "video": {
                "width": { exact: "320" },
                "height": { exact: "240"},
                "frameRate": { min: 10, max: 10 },
                "deviceId": { exact: videoSelect.value}
            }
        }
        navigator.mediaDevices.getUserMedia(constraints).then(gotStream);
    }

    function gotDevices(deviceInfos) {
        for (let i = 0; i !== deviceInfos.length; ++i) {
            const deviceInfo = deviceInfos[i];
            const option = document.createElement('option');
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
    }


    function gotStream(stream) {
        window.stream = stream;
        video.srcObject = stream;
        video.controls = false;
        audio_context = new AudioContext();

        var micinput = audio_context.createMediaStreamSource(stream);

        modulatorInput = audio_context.createGain();
        modulatorGain = audio_context.createGain();
        modulatorGain.gain.value = 4.0;
        modulatorGain.connect( modulatorInput );
        micinput.connect(modulatorGain);

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
                // console.log(elem_range[j]);
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
        
        recorder = new Recorder(micinput);

        var finishVideoSetup_ = function() {
            // Note: video.onloadedmetadata doesn't fire in Chrome when using
            // getUserMedia so we have to use setTimeout. See crbug.com/110938.
            setTimeout(function() {
                video.width = 320;//video.clientWidth;
                video.height = 240;// video.clientHeight;
                // Canvas is 1/2 for performance. Otherwise, getImageData() readback is
                // awful 100ms+ as 640x480.
                canvas.width = video.width;
                canvas.height = video.height;
            }, 1000);
        };

        finishVideoSetup_();
    }

    function record() {
        if (recorder === undefined) { return; }
        var elapsedTime = $('#elasped-time')[0];
        var ctx = canvas.getContext('2d');
        var CANVAS_HEIGHT = canvas.height;
        var CANVAS_WIDTH = canvas.width;

        karaoke.play();
        recording = true;
        startTime = Date.now();

        toggleActivateRecordButton();
        $('select#audioSource')[0].disabled = true;
        $('select#videoSource')[0].disabled = true;
        $('#stop-me')[0].disabled = false;

        recorder.record();
        video_frames = [];
        function captureFrame() {
            if (recording) {
                frame_time = 1000 / framerate;
                window.setTimeout(captureFrame, frame_time);
            }

            ctx.drawImage(video, 0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
            video_frames.push(canvas.toDataURL('image/png'));
        };
        captureFrame();
    };

    function stop() {
        if (recorder === undefined) { return; }
        window.stream.getTracks().forEach(track => track.stop());
        recorder.stop();
        endTime = Date.now();
        recording = false;
        $('#stop-me')[0].disabled = true;
        $('select#audioSource')[0].disabled = false;
        $('select#videoSource')[0].disabled = false;
        toggleActivateRecordButton();

        console.log('frames captured: ' + video_frames.length + ' => ' +
                    (video_frames.length / framerate) + 's video');

        embedVideoPreview();
    };

    function embedVideoPreview(opt_url) {
        var audioDeferred = jQuery.Deferred();

        recorder.exportWAV(function(blob) {
            var fd = new FormData();
            fd.append('recording_id', recording_id);
            fd.append('data', blob);
            fd.append('filename', "audio.wav");
            jQuery.ajax({
                type: 'POST',
                url: window.location,
                data: fd,
                processData: false,
                contentType: false
            }).done(function(data) {
                audioDeferred.resolve();
                console.log(data);
            });
        });

        var fd = new FormData();
        fd.append('recording_id', recording_id);
        for (var i in video_frames) {
            fd.append('framedata', video_frames[i]);
        }

        var videoDeferred = jQuery.ajax({
            type: 'POST',
            url: window.location,
            data: fd,
            processData: false,
            contentType: false
        }).done(function(data) {
            console.log(data);
        });
        jQuery.when(audioDeferred, videoDeferred).then(function(a1, a2) {
            var fd = new FormData();
            fd.append('recording_id', recording_id);
            fd.append('finished', '1');
            jQuery.ajax({
                type: 'POST',
                url: window.location,
                data: fd,
                processData: false,
                contentType: false
            }).done(function(data) {
                window.location = data;
            });
        });
    }

    function initEvents() {
        $('#record-me')[0].addEventListener('click', record);
        //$('#stop-me')[0].addEventListener('click', function () { document.location = document.location });
        $('#stop-me')[0].addEventListener('click', stop);
    }

    navigator.mediaDevices.enumerateDevices().then(gotDevices).then(getStream);
    audioSelect.onchange = getStream;
    videoSelect.onchange = getStream;
    initEvents();

    return {
        stop: stop
    }

});
