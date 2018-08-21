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
    const annotSelectDiv = $('#annotator-select');
    annotSelectDiv.empty();
    let ul = $(getEl('ul'));
    ul.addClass('checkbox-grid');
    annotSelectDiv.append(ul);
    let annotators = GLOBALS.annotators;
    for (annot_name in annotators) {
        let li = $(getEl('li'));
        ul.append(li);
        let annotCheck = makeAnnotatorCheckbox(annotators[annot_name])
        li.append(annotCheck);
    }
}

const makeAnnotatorCheckbox = (annotInfo) => {
    var div = $(getEl('div'));
    var check = $(getEl('input'));
    div.append(check);
    check.attr('type','checkbox');
    check.attr('name', annotInfo.name);
    check.attr('value', annotInfo.name)
    check.attr('checked', 'checked');
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