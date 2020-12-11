function removeAllChildNodes(parent) {
    while (parent.firstChild) {
        parent.removeChild(parent.firstChild);
    }
}


function modifyReq(action, modifydata) {
    $.ajax({
        url: '/api/modify',
        type: 'post',
        data: {
            guildId: currentGuildId,
            action: action,
            modifydata: modifydata
        },
        success: function(resp) {
            loadData();
        }
    })
}


function addPrefix(prefix) {
    data = JSON.stringify({prefix: prefix})
    return modifyReq('prefix.add', data)
}


function removePrefix(prefix) {
    data = JSON.stringify({prefix: prefix})
    return modifyReq('prefix.remove', data)
}


function addStarboard(channelId) {
    data = JSON.stringify({channel: channelId})
    return modifyReq('starboard.add', data)
}


function removeStarboard(channelId) {
    data = JSON.stringify({channel: channelId})
}


function loadData() {
    $.ajax({
        url: '/api/guild-data',
        type: 'GET',
        dataType: 'JSON',
        data: {
            guildId: currentGuildId
        },
        success: function(resp) {
            let guildData = JSON.parse(resp);
            populateData(guildData);
        }
    })
}


function populateData(guildData) {
    let e = document.getElementById('prefix-list');
    removeAllChildNodes(e);
    guildData.prefixes.forEach(function(prefix) {
        let l = document.createElement("li");
        l.className = "list-group-item my-list-group-item d-flex justify-content-between align-items-center";
        l.textContent = prefix
        tag = document.createElement('button');
        tag.className = "badge badge-circle del-prefix";
        tag.textContent = '×';
        tag.onclick = function(e) {
            removePrefix(prefix);
        }
        l.appendChild(tag);
        e.appendChild(l);
    })
}


$(document).ready(function(){
    loadData();
    $("#add-prefix-input").keypress(function(e) {
        if (e.keyCode == 13) {
            addPrefix($("#add-prefix-input").val());
            $("#add-prefix-input").val('');
        }
    })
});
