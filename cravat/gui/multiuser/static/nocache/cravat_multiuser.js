adminMode = false;
noRemDays = null;
noguest = false

function openSubmitPage () {
    location.href = location.protocol + '//' + window.location.host + '/submit/nocache/index.html';
}

function openLoginPage () {
    location.href = location.protocol + '//' + window.location.host + '/server/nocache/login.html';
}

function login () {
    var usernameSubmit = document.getElementById('login_username').value;
    var passwordSubmit = document.getElementById('login_password').value;
    $.ajax({
        url: '/server/login',
        headers: {'Authorization':`Basic ${btoa(usernameSubmit+':'+passwordSubmit)}`},
        success: function (response) {
            if (response.startsWith('guestsuccess_')) {
                /*
                var noRemDays = response.split('_')[1];
                var div = getEl('div');
                var sdiv = getEl('div');
                sdiv.textContent = 'You are logging with a guest account.';
                addEl(div, sdiv);
                addEl(div, getEl('br'));
                var sdiv = getEl('div');
                sdiv.textContent = 'This guest account will be deleted in ' + noRemDays + ' days.';
                addEl(div, sdiv);
                addEl(div, getEl('br'));
                var sdiv = getEl('div');
                sdiv.textContent = 'To keep using this account, please change the username to your email.';
                addEl(div, sdiv);
                msgAccountDiv(div, openSubmitPage);
                */
                openSubmitPage();
            } else if (response == 'success') {
                username = response['email'];
                openSubmitPage();
            } else if (response == 'fail') {
                msgAccountDiv('Login failed');
            }
        }
    });
}

function logout () {
    $.ajax({
        url: '/server/logout',
        success: function (response) {
            openLoginPage();
        }
    });
}

function getPasswordQuestion () {
    var email = document.getElementById('forgotpasswordemail').value;
    $.ajax({
        url: '/server/passwordquestion',
        data: {'email': email},
        success: function (response) {
            var status = response['status'];
            var msg = response['msg'];
            if (status == 'fail') {
                msgAccountDiv(msg);
            } else {
                document.getElementById('forgotpasswordgetquestiondiv').style.display = 'none';
                document.getElementById('forgotpasswordquestion').textContent = msg;
                document.getElementById('forgotpasswordquestionanswerdiv').style.display = 'block';
            }
        }
    });
}

function showSignupDiv () {
    document.getElementById('logindiv').style.display = 'none';
    document.getElementById('signupdiv').style.display = 'block';
}

function showLoginDiv () {
    document.getElementById('logindiv').style.display = 'block';
    document.getElementById('signupdiv').style.display = 'none';
    document.getElementById('forgotpassworddiv').style.display = 'none';
}

function submitForgotPasswordAnswer () {
    var email = document.getElementById('forgotpasswordemail').value;
    var answer = document.getElementById('forgotpasswordanswer').value;
    $.ajax({
        url: '/server/passwordanswer',
        data: {'email': email, 'answer': answer},
        success: function (response) {
            var success = response['success'];
            var msg = response['msg'];
            if (success == true) {
                document.getElementById('forgotpassworddiv').style.display = 'none';
                document.getElementById('forgotpasswordemail').textContent = '';
                document.getElementById('forgotpasswordquestion').textContent = '';
                document.getElementById('forgotpasswordanswer').textContent = '';
                alert('Password has been reset to ' + msg);
                showLoginDiv();
            } else {
                msgAccountDiv(msg);
            }
        }
    });
}

function forgotPassword () {
    document.getElementById('logindiv').style.display = 'none';
    document.getElementById('forgotpasswordquestion').textContent = '';
    document.getElementById('forgotpasswordgetquestiondiv').style.display = 'block';
    document.getElementById('forgotpasswordquestionanswerdiv').style.display = 'none';
    document.getElementById('forgotpassworddiv').style.display = 'block';
}

function changePassword () {
    var div = document.getElementById('changepassworddiv');
    var display = div.style.display;
    if (display == 'flex') {
        display = 'none';
    } else {
        display = 'flex';
    }
    div.style.display = display;
}

function submitNewPassword () {
    var newemail = document.getElementById('changepasswordnewemail').value;
    var oldpassword = document.getElementById('changepasswordoldpassword').value;
    var newpassword = document.getElementById('changepasswordnewpassword').value;
    var retypenewpassword = document.getElementById('changepasswordretypenewpassword').value;
    var emailRegex = RegExp(/^\S+@\S+\.\S+$/);
    if (newemail == '' && newpassword == '') {
        msgAccountDiv('Nothing to change');
        return;
    }
    if (newemail != '' && emailRegex.test(newemail) == false) {
        msgAccountDiv('Invalid username. Please use your email address.');
        return;
    }
    if (newpassword != '' && newpassword != retypenewpassword) {
        msgAccountDiv('New password mismatch');
        return;
    }
    $.ajax({
        url: '/server/changepassword',
        data: {
            'newemail': newemail,
            'oldpassword': oldpassword,
            'newpassword': newpassword
        },
        success: function (response) {
            if (response == 'success') {
                document.getElementById('changepassworddiv').style.display = 'none';
                var div = getEl('div');
                if (newemail != '') {
                    document.querySelector('#userdiv').textContent = newemail;
                    var sdiv = getEl('div');
                    sdiv.textContent = 'Username changed successfully';
                    addEl(div, sdiv);
                    addEl(div, getEl('br'));
                }
                if (newpassword != '') {
                    var sdiv = getEl('div');
                    sdiv.textContent = 'Password changed successfully';
                    addEl(div, sdiv);
                    addEl(div, getEl('br'));
                }
                if (newemail != '') {
                    var sdiv = getEl('div');
                    sdiv.textContent = 'Logging out since the user name has been changed.';
                    addEl(div, sdiv);
                    var sdiv = getEl('div');
                    sdiv.textContent = 'Log in with the new user name.';
                    addEl(div, sdiv);
                    msgAccountDiv(div, logout);
                } else {
                    msgAccountDiv(div);
                }
            } else {
                msgAccountDiv(response);
            }
        }
    });
}

function hideloginsignupdiv () {
    document.getElementById('loginsignupdialog').style.display = 'none';
}

function toggleloginsignupdiv () {
    document.getElementById('logindiv').style.display = 'block';
    document.getElementById('signupdiv').style.display = 'none';
    var dialog = document.getElementById('loginsignupdialog');
    var display = dialog.style.display;
    if (display == 'none') {
        display = 'block';
    } else {
        display = 'none';
    }
    dialog.style.display = display;
}

function closeLoginSignupDialog (evt) {
    document.getElementById("loginsignupdialog").style.display="none";
}

function tryAsGuest () {
    var d = new Date();
    var dateStr = '' + d.getFullYear() + (d.getMonth() + 1).toString().padStart(2, '0') 
            + d.getDate().toString().padStart(2, '0');
    var username = 'guest_' + (Math.random()*10000000000000000).toString(36) + '_' + dateStr;
    var password = (Math.random()*10000000000000000).toString(36);
    var retypepassword = password;
    var question = 'Type 0 as answer';
    var answer = '0';
    processSignup(username, password, retypepassword, question, answer)
}

function signupSubmit () {
    var username = document.getElementById('signupemail').value.trim();
    var password = document.getElementById('signuppassword').value.trim();
    var retypepassword = document.getElementById('signupretypepassword').value.trim();
    var question = document.getElementById('signupquestion').value.trim();
    var answer = document.getElementById('signupanswer').value.trim();
    processSignup(username, password, retypepassword, question, answer)
}

function processSignup(username, password, retypepassword, question, answer) {
    if (!username.match(/^\S+@\S+\.\S+$/) && username != "admin" && !username.includes("guest_")) {
        msgAccountDiv('Invalid email.')
        return
    }
    if (password == '') {
        msgAccountDiv('Password is empty.')
        return
    }
    if (retypepassword == '') {
        msgAccountDiv('Re-typed password is empty.')
        return
    }
    if (question == '') {
        msgAccountDiv('Question is empty.')
        return
    }
    if (answer == '') {
        msgAccountDiv('Answer is empty.')
        return
    }
    if (password != retypepassword) {
        msgAccountDiv('Password mismatch')
        return;
    }
    $.ajax({
        url: '/server/signup',
        data: {'username': username, 'password': password, 'question': question, 'answer': answer},
        success: function (response) {
            if (response == 'Signup successful') {
                document.getElementById('login_username').value = username;
                document.getElementById('login_password').value = password;
                msgAccountDiv(response, login)
            } else {
                msgAccountDiv(response, null)
            }
        },
        error: function(response) {
            msgAccountDiv(response, null)
        }
    });
}

function checkLogged (inUsername) {
    $.ajax({
        url: '/server/checklogged',
        data: {'username': inUsername},
        success: function (response) {
            logged = response['logged'];
            if (logged == true) {
                username = response['email'];
                noRemDays = response['days_rem'];
                adminMode = response['admin']
                doAfterLogin(username);
            } else {
                showUnloggedControl();
            }
        }
    });
}

function showLoggedControl (username) {
    addAccountDiv(username);
}

function showUnloggedControl () {
    openLoginPage();
}

function doAfterLogin (username) {
    showLoggedControl(username);
    if (adminMode == true) {
        setupAdminMode();
    }
    populateJobs();
}

function setupAdminMode () {
    document.getElementById('settingsdiv').style.display = 'none';
    document.querySelector('.threedotsdiv').style.display = 'block';
    $('#storediv_tabhead[value=storediv]')[0].style.display = 'inline-block';
    $('#admindiv_tabhead[value=admindiv]')[0].style.display = 'inline-block';
    document.getElementById('admindiv_tabhead').setAttribute('disabled', 'f');
    document.getElementById('submitcontentdiv').style.display = 'none';
    populateAdminTab();
}

function getDateStr (d) {
    var year = d.getFullYear();
    var month = d.getMonth() + 1;
    if (month < 10) {
        month = '0' + month;
    } else {
        month = '' + month;
    }
    var day = d.getDate();
    if (day < 10) {
        day = '0' + day;
    } else {
        day = '' + day;
    }
    var datestr = year + '-' + month + '-' + day;
    return datestr;
}

function populateAdminTab () {
    var div = document.getElementById('admindiv');
    // date range
    var sdiv = getEl('div');
    sdiv.className = 'adminsection-div';
    var span = getEl('span');
    span.className = 'adminsection-title';
    span.textContent = 'Date range';
    addEl(sdiv, span);
    var ssdiv = getEl('div');
    var input = getEl('input');
    input.id = 'admindiv-startdate-input';
    input.type = 'date';
    input.style.marginLeft = '10px';
    var startDate = new Date();
    var startDate = new Date(startDate.setDate(startDate.getDate() - 7));
    var datestr = getDateStr(startDate);
    input.value = datestr;
    addEl(ssdiv, input);
    var span = getEl('span');
    span.textContent = '~';
    span.style.marginLeft = '10px';
    addEl(ssdiv, span);
    var input = getEl('input');
    input.id = 'admindiv-enddate-input';
    input.type = 'date';
    input.style.marginLeft = '10px';
    var datestr = getDateStr(new Date());
    input.value = datestr;
    addEl(ssdiv, input);
    var btn = getEl('button');
    btn.classList.add('butn');
    btn.textContent = 'Update';
    btn.style.marginLeft = '10px';
    btn.addEventListener('click', function (evt) {
        updateAdminTabContent();
    });
    addEl(ssdiv, btn);
    var btn = getEl('button');
    btn.classList.add('butn');
    btn.textContent = 'Export';
    btn.style.marginLeft = '10px';
    btn.addEventListener('click', function (evt) {
        exportContentAdminPanel();
    });
    addEl(ssdiv, btn);
    addEl(sdiv, ssdiv);
    addEl(div, sdiv);
    // input stat
    var sdiv = getEl('div');
    sdiv.id = 'admindiv-inputstat-div';
    sdiv.className = 'adminsection-div';
    addEl(div, sdiv);
    var span = getEl('span');
    span.className = 'adminsection-title';
    span.textContent = 'Input Stats';
    addEl(sdiv, span);
    var ssdiv = getEl('div');
    ssdiv.id = 'admindiv-inputstat-contentdiv';
    addEl(sdiv, ssdiv);
    // job stat
    var sdiv = getEl('div');
    sdiv.id = 'admindiv-jobstat-div';
    sdiv.className = 'adminsection-div';
    addEl(div, sdiv);
    var span = getEl('span');
    span.className = 'adminsection-title';
    span.textContent = 'Job Stats';
    addEl(sdiv, span);
    var ssdiv = getEl('div');
    ssdiv.id = 'admindiv-jobstat-contentdiv';
    addEl(sdiv, ssdiv);
    // user stat
    var sdiv = getEl('div');
    sdiv.id = 'admindiv-userstat-div';
    sdiv.className = 'adminsection-div';
    addEl(div, sdiv);
    var span = getEl('span');
    span.className = 'adminsection-title';
    span.textContent = 'User Stats';
    addEl(sdiv, span);
    var ssdiv = getEl('div');
    ssdiv.id = 'admindiv-userstat-contentdiv';
    addEl(sdiv, ssdiv);
    // annotation stat
    var sdiv = getEl('div');
    sdiv.id = 'admindiv-annotstat-div';
    sdiv.className = 'adminsection-div';
    addEl(div, sdiv);
    var span = getEl('span');
    span.className = 'adminsection-title';
    span.textContent = 'Annotation Stats';
    addEl(sdiv, span);
    var ssdiv = getEl('div');
    ssdiv.id = 'admindiv-annotstat-contentdiv';
    addEl(sdiv, ssdiv);
    // assembly stat
    var sdiv = getEl('div');
    sdiv.id = 'admindiv-assemblystat-div';
    sdiv.className = 'adminsection-div';
    addEl(div, sdiv);
    var span = getEl('span');
    span.className = 'adminsection-title';
    span.textContent = 'Assembly Stats';
    addEl(sdiv, span);
    var ssdiv = getEl('div');
    ssdiv.id = 'admindiv-assemblystat-contentdiv';
    addEl(sdiv, ssdiv);
    // Restart button
    var btn = getEl('button');
    btn.textContent = 'Restart Server';
    btn.addEventListener('click', function (evt) {
        var url = '/server/restart';
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
        xhr.send();
        location.href = '/server/nocache/login.html';
    });
    addEl(sdiv, btn);
    addEl(div, getEl('br'));
    // Final
    updateAdminTabContent();
}

function updateAdminTabContent () {
    populateInputStatDiv();
    populateUserStatDiv();
    populateJobStatDiv();
    populateAnnotStatDiv();
    populateAssemblyStatDiv();
}

function populateInputStatDiv () {
    var startDate = document.getElementById('admindiv-startdate-input').value;
    var endDate = document.getElementById('admindiv-enddate-input').value;
    var sdiv = document.getElementById('admindiv-inputstat-contentdiv');
    $(sdiv).empty();
    var table = getEl('table');
    addEl(sdiv, table);
    $.ajax({
        url: '/server/inputstat',
        data: {'start_date':startDate, 'end_date':endDate},
        success: function (response) {
            var totN = response[0];
            var maxN = response[1];
            var avgN = response[2];
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Total number of input lines:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = totN;
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Maximum number of input lines:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = maxN;
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Average number of input lines:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = Math.round(avgN);
            addEl(tr, td);
            addEl(table, tr);
        },
    });
}

function populateUserStatDiv () {
    var startDate = document.getElementById('admindiv-startdate-input').value;
    var endDate = document.getElementById('admindiv-enddate-input').value;
    var sdiv = document.getElementById('admindiv-userstat-contentdiv');
    $(sdiv).empty();
    var table = getEl('table');
    addEl(sdiv, table);
    $.ajax({
        url: '/server/userstat',
        data: {'start_date':startDate, 'end_date':endDate},
        success: function (response) {
            //
            var num_uniq_user = response['num_uniq_user'];
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Number of unique users:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = num_uniq_user;
            addEl(tr, td);
            addEl(table, tr);
            //
            var frequent = response['frequent'];
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Most frequent user:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = frequent[0];
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = '\xa0\xa0Number of jobs:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = frequent[1];
            addEl(tr, td);
            addEl(table, tr);
            //
            var heaviest = response['heaviest'];
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Heaviest user:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = heaviest[0];
            addEl(tr, td);
            addEl(table, tr);
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = '\xa0\xa0Number of input:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = heaviest[1];
            addEl(tr, td);
            addEl(table, tr);
        },
    });
}

function populateJobStatDiv () {
    var startDate = document.getElementById('admindiv-startdate-input').value;
    var endDate = document.getElementById('admindiv-enddate-input').value;
    var sdiv = document.getElementById('admindiv-jobstat-contentdiv');
    $(sdiv).empty();
    var table = getEl('table');
    addEl(sdiv, table);
    var canvas = getEl('canvas');
    addEl(sdiv, canvas);
    $.ajax({
        url: '/server/jobstat',
        data: {'start_date':startDate, 'end_date':endDate},
        success: function (response) {
            //
            var num_jobs = response['num_jobs'];
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Total number of jobs:\xa0';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = num_jobs;
            addEl(tr, td);
            addEl(table, tr);
            var chartdata = response['chartdata'];
            var submits = chartdata[0];
            var counts = chartdata[1];
			var chart = new Chart(canvas, {
				type: 'bar',
				data: {
					datasets: [{
						data: counts,
					}],
					labels: submits,
				},
                options: {
                    scales: {
                        xAxes: [{
                            type: 'time',
                            time: {
                                unit: 'day',
                            },
                            scaleLabel: {
                                display: true,
                                labelString: 'Date',
                            },
                        }],
                        yAxes: [{
                            ticks: {
                                min: 0,
                            },
                            scaleLabel: {
                                display: true,
                                labelString: 'Number of Jobs',
                            },
                        }],
                    },
                    elements: {
                        line: {
                            tension: 0,
                        },
                    },
                    legend: {
                        display: false,
                    },
                },
			});
        },
    });
}

function populateAnnotStatDiv () {
    var startDate = document.getElementById('admindiv-startdate-input').value;
    var endDate = document.getElementById('admindiv-enddate-input').value;
    var sdiv = document.getElementById('admindiv-annotstat-contentdiv');
    $(sdiv).empty();
    sdiv.style.width = '800px';
    sdiv.style.height = '700px';
    var table = getEl('table');
    addEl(sdiv, table);
    var chartdiv = getEl('canvas');
    chartdiv.id = 'admindiv-annotstat-chart1';
    addEl(sdiv, chartdiv);
    $.ajax({
        url: '/server/annotstat',
        data: {'start_date':startDate, 'end_date':endDate},
        success: function (response) {
            //
            var annotCount = response['annot_count'];
            var annots = Object.keys(annotCount);
            for (var i = 0; i < annots.length - 1; i++) {
                for (var j = i + 1; j < annots.length; j++) {
                    if (annotCount[annots[i]] < annotCount[annots[j]]) {
                        var tmp = annots[i];
                        annots[i] = annots[j];
                        annots[j] = tmp;
                    }
                }
            }
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Module';
            td.style.textDecoration = 'underline';
            td.style.textDecorationColor = '#aaaaaa';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = 'Number of jobs';
            td.style.textDecoration = 'underline';
            td.style.textDecorationColor = '#aaaaaa';
            addEl(tr, td);
            addEl(table, tr);
            var tbody = getEl('tbody');
            addEl(table, tbody);
            var counts = [];
            for (var i = 0; i < annots.length; i++) {
                var tr = getEl('tr');
                var td = getEl('td');
                td.textContent = annots[i];
                addEl(tr, td);
                var td = getEl('td');
                td.textContent = annotCount[annots[i]];
                counts.push(annotCount[annots[i]]);
                addEl(tr, td);
                addEl(table, tr);
            }
			var chart = new Chart(chartdiv, {
				type: 'doughnut',
				data: {
					datasets: [{
						data: counts,
					}],
					labels: annots,
				},
			});
        },
    });
}

function populateAssemblyStatDiv () {
    var startDate = document.getElementById('admindiv-startdate-input').value;
    var endDate = document.getElementById('admindiv-enddate-input').value;
    var sdiv = document.getElementById('admindiv-assemblystat-contentdiv');
    $(sdiv).empty();
    var table = getEl('table');
    addEl(sdiv, table);
    $.ajax({
        url: '/server/assemblystat',
        data: {'start_date':startDate, 'end_date':endDate},
        success: function (response) {
            var thead = getEl('thead');
            var tr = getEl('tr');
            var td = getEl('td');
            td.textContent = 'Genome assembly';
            td.style.textDecoration = 'underline';
            td.style.textDecorationColor = '#aaaaaa';
            addEl(tr, td);
            var td = getEl('td');
            td.textContent = 'Number of jobs';
            td.style.textDecoration = 'underline';
            td.style.textDecorationColor = '#aaaaaa';
            addEl(tr, td);
            addEl(table, tr);
            var tbody = getEl('tbody');
            addEl(table, tbody);
            for (var i = 0; i < response.length; i++) {
                var tr = getEl('tr');
                var td = getEl('td');
                td.textContent = response[i][0];
                addEl(tr, td);
                var td = getEl('td');
                td.textContent = response[i][1];
                addEl(tr, td);
                addEl(table, tr);
            }
        },
    });
}

function msgAccountDiv (msg, callback) {
    var div = getEl('div');
    if (typeof msg == 'string') {
        div.textContent = msg;
    } else if (typeof msg == 'object') {
        addEl(div, msg);
    }
    showYesNoDialog(div, callback, false, true);
}

function isGuestAccount (username) {
    if (username.startsWith('guest_') && username.indexOf('@') == -1) {
        return true;
    } else {
        return false;
    }
}

function addAccountDiv (username) {
    var div = document.querySelector('#accountdiv');
    if (div != null) {
        div.remove();
    }
    var div = getEl('div');
    div.id = 'accountdiv';
    var userDiv = getEl('span');
    userDiv.id = 'userdiv';
    userDiv.textContent = username + '\xa0';
    addEl(div, userDiv);
    var logoutDiv = getEl('div');
    logoutDiv.id = 'logdiv';
    addEl(div, logoutDiv);
    var btn = getEl('img');
    btn.src = '/server/pwchng.png';
    btn.addEventListener('click', function (evt) {
        changePassword();
    });
    btn.title = 'Change password';
    addEl(logoutDiv, btn);
    var span = getEl('span');
    span.textContent = '\xa0\xa0';
    addEl(logoutDiv, span);
    var btn = getEl('img');
    btn.src = '/server/logout.png';
    btn.addEventListener('click', function (evt) {
        logout();
    });
    btn.title = 'Logout';
    addEl(logoutDiv, btn);
    var sdiv = getEl('div');
    sdiv.id = 'changepassworddiv';
    var span = getEl('span');
    span.textContent = 'Current password: ';
    addEl(sdiv, span);
    var input = getEl('input');
    input.type = 'password';
    input.id = 'changepasswordoldpassword';
    addEl(sdiv, input);
    addEl(sdiv, getEl('br'));
    var span = getEl('span');
    span.textContent = 'New email: ';
    addEl(sdiv, span);
    var input = getEl('input');
    input.type = 'text';
    input.id = 'changepasswordnewemail';
    addEl(sdiv, input);
    addEl(sdiv, getEl('br'));
    var span = getEl('span');
    span.textContent = 'New password: ';
    addEl(sdiv, span);
    var input = getEl('input');
    input.type = 'password';
    input.id = 'changepasswordnewpassword';
    addEl(sdiv, input);
    addEl(sdiv, getEl('br'));
    var span = getEl('span');
    span.textContent = 'Retype new password: ';
    addEl(sdiv, span);
    var input = getEl('input');
    input.type = 'password';
    input.id = 'changepasswordretypenewpassword';
    addEl(sdiv, input);
    addEl(sdiv, getEl('br'));
    var btn = getEl('button');
    btn.classList.add('butn');
    btn.addEventListener('click', function (evt) {
        submitNewPassword();
    });
    btn.textContent = 'Submit';
    addEl(sdiv, btn);
    addEl(div, sdiv);
    var headerDiv = document.querySelector('.headerdiv');
    addEl(headerDiv, div);
    if (isGuestAccount(username)) {
        document.querySelector('#changepassworddiv input:nth-child(2)').style.display = 'none';
        document.querySelector('#changepassworddiv span:first-child').style.display = 'none';
        var sdiv = getEl('div');
        sdiv.id = 'guest_warn_div';
        var span = getEl('span');
        span.textContent = 'This guest account will be deleted after ' + noRemDays + (noRemDays > 1? ' days': ' day') + '. To keep your jobs, click the change account information icon to the right of user name and enter your email address and a new password.';
        addEl(sdiv, span);
        addEl(div, sdiv);
        var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.style.marginRight = '0.2rem';
        svg.addEventListener('mouseover', function (evt) {
            document.querySelector('#guest_warn_div').style.display = 'flex';
        });
        svg.addEventListener('mouseout', function (evt) {
            document.querySelector('#guest_warn_div').style.display = 'none';
        });
        svg.setAttribute('version', '1.1');
        svg.setAttribute('viewBox', '0 0 100 100');
        svg.setAttribute('width', '24');
        svg.setAttribute('height', '24');
        var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', '50');
        c.setAttribute('cy', '50');
        c.setAttribute('r', '50');
        c.setAttribute('fill', '#ff0000');
        addEl(svg, c);
        var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', '50');
        c.setAttribute('cy', '80');
        c.setAttribute('r', '10');
        c.setAttribute('fill', '#ffffff');
        addEl(svg, c);
        var c = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        c.setAttribute('d', 'M38,24 A12,12,0,0,1,62,24 L56,62 A8,8,0,0,1,44,62');
        c.setAttribute('fill', '#ffffff');
        addEl(svg, c);
        div.prepend(svg);
        //var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        //path.setAttribute('d', 'M0,0 Lee
        /*
        var sdiv = getEl('div');
        sdiv.textContent = 'You are logging with a guest account.';
        addEl(div, sdiv);
        addEl(div, getEl('br'));
        var sdiv = getEl('div');
        sdiv.textContent = 'This guest account will be deleted in ' + noRemDays + ' days.';
        addEl(div, sdiv);
        addEl(div, getEl('br'));
        var sdiv = getEl('div');
        sdiv.textContent = 'To keep using this account, please change the username to your email.';
        addEl(div, sdiv);
        */
    }
}

function exportContentAdminPanel (tabName) {
	var content = '';
	document.querySelectorAll('.adminsection-div').forEach(function (div) {
		var title = div.querySelector('span').textContent;
		content += '* ' + title + '\n';
		var contentDiv = div.querySelector('div');
		var table = contentDiv.querySelector('table');
		if (table != undefined) {
			var trs = table.querySelectorAll('tr');
			for (var i = 0; i < trs.length; i++) {
				var tr = trs[i];
				var tds = tr.querySelectorAll('td');
				var line = '';
				for (var j = 0; j < tds.length; j++) {
					var td = tds[j];
					line += td.textContent.replace(/\xa0/g, ' ') + '\t';
				}
				content += line + '\n';
			}
		} else {
			var line = '';
			var sdivs = contentDiv.children;
			for (var i = 0; i < sdivs.length; i++) {
				var sdiv = sdivs[i];
				var tagName = sdiv.tagName;
				if (tagName == 'BUTTON') {
					continue;
				}
				var value = sdiv.textContent;
				if (tagName == 'INPUT') {
					value = sdiv.value;
				}
				line += value + '\t';
			}
			content += line + '\n';
		}
		content += '\n';
	});
	content += '\n';
	var a = getEl('a');
	a.href = window.URL.createObjectURL(
			new Blob([content], {type: 'text/tsv'}));
	a.download = 'OpenCRAVAT_admin_stats.tsv';
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
}

function multiuser_run () {
    var submitBtn = document.querySelector('#login_button');
    var el = document.querySelector('#login_username');
    el.addEventListener('keyup', function (evt) {
        if (evt.which == 13 || evt.keyCode == 13) {
            login();
        }
    });
    var el = document.querySelector('#login_password');
    el.addEventListener('keyup', function (evt) {
        if (evt.which == 13 || evt.keyCode == 13) {
            login();
        }
    });
}

window.onload = function(evt) {
    fetch('/server/noguest').then(function(response) {
        if (response.status != 200) {
            return false
        } else {
            return response.json()
        }
    }).then(function(response) {
        noguest = response
        if (!noguest) {
            document.querySelector('#guestdiv').classList.add('show')
        }
    })
}

