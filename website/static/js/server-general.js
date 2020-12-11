function modifyReq(action, modifydata) {
    return $.ajax({
        url: '/api/modify',
        type: 'post',
        data: {
            guildId: currentGuildId,
            action: action,
            modifydata: modifydata
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
    console.log(guildData);
    div = document.getElementById("prefixes");
    div.textContent = String(guildData.prefixes);
}


$(document).ready(function(){
    $(".show-toast").click(function(){
        $("#myToast").toast('show');
    });
    loadData();
});
