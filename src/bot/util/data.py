import json
import glob
import pandas as pd


def get_games(tournament_dir, topN=None, player_names=None):
    try:
        players = pd.read_csv(tournament_dir + 'players.csv', index_col=0)
        players.columns = ['bot_name', 'score', 'final_stack', 'games']
        players.index.name = 'user'
        names = pd.Series(players['bot_name'].index.values, index=players['bot_name'])
    except FileNotFoundError:
        players = None
        names = None

    if player_names is not None:
        filter_seats = player_names
    elif topN is not None:
        filter_seats = list(players.head(topN).index)
    else:
        filter_seats = []

    for filename in glob.iglob(tournament_dir + '*.json'):
        with open(filename) as f:
            game = json.load(f)
            gg = False

            for seat in game['seats']:
                if names is not None:
                    seat['name'] = names.loc[seat['name']]

                seat['top_player'] = False
                if len(filter_seats) > 0:
                    if seat['name'] in filter_seats:
                        gg = True
                        seat['top_player'] = True
                else:
                    gg = True

            if gg:
                yield game


def stack_Xy(data_dir, num):
    X = pd.read_pickle(data_dir + 'X0.pickle')
    y = pd.read_pickle(data_dir + 'y0.pickle')

    for i in range(1, num):
        X = X.append(pd.read_pickle(data_dir + 'X' + str(i) + '.pickle'))
        y = y.append(pd.read_pickle(data_dir + 'y' + str(i) + '.pickle'))

    X.index = range(len(X))
    y.index = range(len(y))

    X.to_pickle(data_dir + 'X.pickle')
    y.to_pickle(data_dir + 'y.pickle')

    return X, y
