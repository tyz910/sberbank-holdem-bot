String.prototype.replaceAll = function(search, replacement) {
    var target = this;
    return target.replace(new RegExp(search, 'g'), replacement);
};

var cardNames = {
    'first': {
        'H': 'hearts',
        'S': 'spades',
        'C': 'clubs',
        'D': 'diamonds'
    },
    'second': {
        'K': 'king',
        'Q': 'queen',
        'J': 'jack',
        'A': 'ace',
        'T': '10'
    }
};

function cardToImg(card) {
    var name = card.split('');

    var first = cardNames['first'][name[0]];
    var second = (cardNames['second'][name[1]]) ? cardNames['second'][name[1]] : name[1];

    return 'cards/' + second + '_of_' + first + '.png';
}

function drawCards(cards, container) {
    container.html('');
    $.each(cards, function (i, c) {
        var img = $('<img class="poker-card" src="' + cardToImg(c) + '" title="' + c + '">');
        container.append(img);
    });
}

function initSeats(seats) {
    var container = $('#seats');
    container.html('');
    var rowTpl = $('#seats_head');
    rowTpl = rowTpl.prop('outerHTML')
        .replaceAll('<th', '<td')
        .replaceAll('</th>', '</td>')
        .replaceAll('id="seats_head"', '')
    ;

    $.each(seats, function (i, s) {
        var row = $(rowTpl);

        row.attr('id', 'seat_uuid_' + s.uuid);
        row.attr('data-uuid', s.uuid);
        row.find('.seats_num').html('<strong>' + s.name + '</strong>');

        container.append(row);
    });
}

function drawSeats(seats, sbUuid, bbUuid) {
    $.each(seats, function (i, s) {
        var row = $('#seat_uuid_' + s.uuid);

        var stackHtml = '<big>' + s.stack + '</big><br>';
        var stackDiff =  s.stack - s.start_stack;

        if (s.uuid == sbUuid) {
            stackDiff -= 15;
        }

        if (s.uuid == bbUuid) {
            stackDiff -= 30;
        }

        if (stackDiff != 0) {
            if (stackDiff > 0) {
                stackDiff = '+' + stackDiff;
            }
            stackHtml += '<small>' + stackDiff + '</small>';
        }

        row.find('.seats_stack').html(stackHtml);
        row.find('.seats_state').html(s.state);

        row.find('.seats_action_preflop').html('');
        row.find('.seats_action_flop').html('');
        row.find('.seats_action_turn').html('');
        row.find('.seats_action_river').html('');

        if (s.hole_card) {
            drawCards(s.hole_card, row.find('.seats_hole_card'))
        }

        row.removeClass('table-secondary table-success table-danger table-warning');

        if (s.start_state == 'folded') {
            row.addClass('table-secondary');
        }

        if ((s.state == 'participating') && (s.stack - s.start_stack < 0)) {
            row.addClass('table-warning');
        }

        if ((s.state == 'allin') && (s.stack - s.start_stack < 0)) {
            row.addClass('table-danger');
        }
    });
}

function drawGame(game) {
    initSeats(game.seats);
    drawRound(game.rounds[0]);
}

function drawRound(round) {
    var sbUuid = bbUuid = '';
    $.each(round.round_state.action_histories['preflop'], function (j, a) {
        if (a.action == 'SMALLBLIND') {
            sbUuid = a.uuid;
        }

        if (a.action == 'BIGBLIND') {
            bbUuid  = a.uuid;
        }
    });

    drawCards(round.round_state.community_card, $('#community_card'));
    drawSeats(round.round_state.seats, sbUuid, bbUuid);

    $.each(round.winners, function (i, s) {
        var row = $('#seat_uuid_' + s.uuid);

        row.removeClass('table-danger table-warning').addClass('table-success');
    });

    $.each(round.round_state.seats, function (i, s) {
        if (i == round.round_state.dealer_btn) {
            var row = $('#seat_uuid_' + s.uuid).find('.seats_action_preflop');
            addAction(row, 'DEALER', 0);
        }
    });

    $.each(['preflop', 'flop', 'turn', 'river'], function (i, stage) {
        if (round.round_state.action_histories[stage]) {
            $.each(round.round_state.action_histories[stage], function (j, a) {
                var uuid = a.uuid;
                var action = a.action;
                var amount = a.amount ? a.amount : 0;

                var row = $('#seat_uuid_' + uuid).find('.seats_action_' + stage);
                addAction(row, action, amount);
            });
        }
    });
}

function addAction(container, action, amount) {
    var div = $('<div></div>');
    var label = $('<span class="badge">' + action + ': ' + amount + '</span>');

    var classes = {
        'FOLD': 'badge-secondary',
        'BIGBLIND': 'badge-info',
        'SMALLBLIND': 'badge-info',
        'DEALER': 'badge-info',
        'RAISE': 'badge-warning'
    };

    if (classes[action]) {
        label.addClass(classes[action]);
    } else {
        label.addClass('badge-primary');
    }

    div.append(label);
    container.append(div);
}
