console.log('submit.js');

var GLOBALS = {
    allJobs: [],
    annotators: {}
}

const submit = () => {
    console.log('submit the form');
    let fd = new FormData();
    const fileInputElem = $('#input-file')[0];
    const inputFile = fileInputElem.files[0];
    fd.append('file', inputFile);
    var submitOpts = {
        'annotators': []
    }
    const annotCheckBoxes = $('.annotator-checkbox');
    for (var i = 0; i<annotCheckBoxes.length; i++){
        const cb = annotCheckBoxes[i];
        if (cb.checked) {
            submitOpts.annotators.push(cb.value);
        }
    }
    submitOpts.assembly = $('#assembly-select').val();
    fd.append('options',JSON.stringify(submitOpts));
    $.ajax({
        url:'/rest/submit',
        data: fd,
        type: 'POST',
        processData: false,
        contentType: false,
        success: function (data) {
            GLOBALS.allJobs.push(data);
            $('#job-view-selector').val(data);
            buildJobsTable();
        }
    })
};

const buildJobsTable = () => {
    let allJobs = GLOBALS.allJobs;
    let jobsTable = $('#jobs-table');
    // Remove all but header row
    jobsTable.slice(1).remove();
    for (let i = 0; i < allJobs.length; i++) {
        job = allJobs[i];
        let jobTr = $(getEl('tr'));
        jobsTable.append(jobTr);
        let viewTd = $(getEl('td'));
        jobTr.append(viewTd);
        let viewBtn = $(getEl('button')).append('View');
        viewBtn.attr('disabled', !job.viewable);
        viewBtn.attr('jobId', job.id);
        viewBtn.click(jobViewButtonHandler);
        viewTd.append(viewBtn);
        jobTr.append($(getEl('td')).append(job.orig_input_fname));
        jobTr.append($(getEl('td')).append(job.submission_time.toLocaleString()));
        jobTr.append($(getEl('td')).append(job.id));
    }
}

const getEl = (tag) => {
    return document.createElement(tag);
}

const viewJob = (jobId) => {
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

const jobViewButtonHandler = (event) => {
    const jobId = $(event.target).attr('jobId');
    viewJob(jobId);
}

const addListeners = () => {
    $('#submit-job-button').click(submit);
}

var JOB_IDS = []

const populateJobs = () => {
    $.ajax({
        url:'/rest/jobs',
        type: 'GET',
        success: function (allJobs) {
            for (var i=0; i<allJobs.length; i++) {
                let job = allJobs[i];
                const trueDate = new Date(job.submission_time);
                job.submission_time = trueDate;
            }
            GLOBALS.allJobs = allJobs
            buildJobsTable();
        }
    })
}

const populateAnnotators = () => {
    $.ajax({
        url:'/rest/annotators',
        type: 'GET',
        success: function (data) {
            GLOBALS.annotators = data
            rebuildAnnotatorsSelector();
        }
    })
}

const rebuildAnnotatorsSelector = () => {
    let flexbox = $('#annotator-flexbox');
    flexbox.empty();
    let annotators = GLOBALS.annotators;
    let annotInfos = Object.values(annotators);
    // Sort by title
    annotInfos.sort((a,b) => {
        var x = a.title.toLowerCase();
        var y = b.title.toLowerCase();
        if (x < y) {return -1;}
        if (x > y) {return 1;}
        return 0;
    });
    // Add divs
    let annotDivs = [];
    for (let i=0; i<annotInfos.length; i++) {
        const annotInfo = annotInfos[i];
        let annotDiv = makeAnnotatorCheckbox(annotInfo);
        flexbox.append(annotDiv);
        annotDivs.push(annotDiv);
    }
    // Resize all to match max
    const maxWidth = Math.max.apply(null, annotDivs.map(elem => elem.width()));
    for (let i=0; i<annotDivs.length; i++) {
        let annotDiv = annotDivs[i];
        annotDiv.width(maxWidth);
    }
}

const makeAnnotatorCheckbox = (annotInfo) => {
    var div = $(getEl('div'));
    var check = $(getEl('input'));
    div.append(check);
    check.addClass('annotator-checkbox');
    check.attr('type','checkbox');
    check.attr('name', annotInfo.name);
    check.attr('value', annotInfo.name)
    check.attr('checked', true);
    var label = $(getEl('label'));
    check.after(label);
    label.attr('for',annotInfo.name);
    label.append(annotInfo.title)
    // div.append(annotInfo.title);
    return div;
}

const run = () => {
    console.log('run');
    addListeners();
    populateAnnotators();
    populateJobs();
};