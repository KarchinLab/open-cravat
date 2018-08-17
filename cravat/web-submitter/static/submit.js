console.log('submit.js');

var GLOBALS = {
    allJobs: []
}

const submit = () => {
    console.log('submit the form');
    let fd = new FormData();
    const fileInputElem = $('#input-file')[0];
    const inputFile = fileInputElem.files[0];
    fd.append('file', inputFile);
    let entries = fd.entries();
    console.log(entries.next());
    $.ajax({
        url:'/rest/submit',
        data: fd,
        type: 'POST',
        processData: false,
        contentType: false,
        success: function (data) {
            GLOBALS.allJobs.push(data);
            rebuildJobSelector();
            $('#job-view-selector').val(data);
        }
    })
};

const getEl = (tag) => {
    return document.createElement(tag);
}

const rebuildJobSelector = () => {
    const jobSelector = $('#job-view-selector');
    jobSelector.empty();
    for (let i=0; i<GLOBALS.allJobs.length; i++) {
        const job = GLOBALS.allJobs[i];
        const jobId = job.id;
        let opt = getEl('option')
        opt.value = jobId;
        opt.innerText = jobId;
        jobSelector.append(opt);
    }
    jobSelector.val(GLOBALS.allJobs.slice(-1));
}

const jobViewButtonHandler = (event) => {
    const jobSelector = $('#job-view-selector');
    const jobId = jobSelector.val();
    var jsonObj = {'jobId':jobId};
    $.ajax({
        url:'/rest/view',
        data: JSON.stringify(jsonObj),
        type: 'POST',
        processData: false,
        contentType: 'application/json',
        success: function (data) {
            console.log(data);
        }
    })
}

const addListeners = () => {
    console.log('addListeners');
    $('#submit-job-button').click(submit);
    $('#job-view-button').click(jobViewButtonHandler);
}

var JOB_IDS = []

const populateJobs = () => {
    $.ajax({
        url:'/rest/jobs',
        type: 'GET',
        success: function (data) {
            GLOBALS.allJobs = data
            rebuildJobSelector();
        }
    })
}

const run = () => {
    console.log('run');
    addListeners();
    populateJobs();
};