import numpy as np
import pandas as pd
import ta

def add_EMA_as_column(token, p, df):
    # p is a number
    price = df[token + 'Close'].values  # returns an np price, faster

    ema = np.empty_like(price)
    k = 2/(p - 1)
    for i, item in enumerate(np.nditer(price)):
        if i == 0:
            ema[i] = item
        elif i < p: #EMA
            ema[i] = price[0:i].mean()
        else:
            ema[i] = price[i]*k + ema[i-1]*(1- k) #price[(i - p):i].mean()

    col_name = 'EMA_' + str(p)
    df[col_name] = ema  # modifies the input df
    df[col_name] = df[col_name] - df[token + 'Close']


def add_renko(blocksize, token):
    #reference for how bricks are calculated https://www.tradingview.com/wiki/Renko_Charts
    # p is a number
    prices = df[token + 'Close'].values  # returns an np price, faster

    renko = np.empty_like(prices)

    indicator_val = 0
    #Loop to calculate the renko value at each data point
    for i, price in enumerate(np.nditer(prices)):
        if i == 0:
            upper_thresh = price + blocksize
            lower_thresh = price - blocksize
        elif price <= lower_thresh: #create a down block

            indicator_val -= blocksize #continuing a downtrend
            lower_thresh -= blocksize
            upper_thresh = lower_thresh + 3*blocksize

        elif price >= upper_thresh: #create an up block

            indicator_val += blocksize #continuing an uptrend
            upper_thresh += blocksize
            lower_thresh = upper_thresh - 3*blocksize

            renko[i] = indicator_val

        period = 5
        indicator = np.empty_like(prices)

    # #Loop to interpret the renko to be more useful
    # for i, item in enumerate(renko):
    #     if i == 0:
    #         indicator[i] = item
    #     elif i < period:
    #         indicator[i] = renko[0:i].mean()
    #     else:
    #         indicator[i] = renko[(i - period):i].mean() - renko[i-period]

    df['Renko'] = renko


def add_sentiment(mydata):
    """This function pulls sentiment data from the crypto fear and greed index. That data is updated daily.
    This is the link to the website: https://alternative.me/crypto/fear-and-greed-index/#fng-history
    The 'limit' argument is the number of data points to fetch (one for each day).
    The given value is on a scale of 0 - 100, with 0 being extreme fear and 100 being extreme greed."""


    #Get the oldest date and figure out how long ago it was
    days = (datetime.now() - mydata.Date.min()).days + 1 #validated this is correct
    url = "https://api.alternative.me/fng/?limit="+ str(days) +"&date_format=us"

    data = requests.get(url).json()["data"] #returns a list of dictionaries

    sentiment_df = pd.DataFrame(data)

    #Drop unnecessaary columns
    sentiment_df.drop(columns = ["time_until_update", "value_classification"], inplace = True)
    #Rename the columns
    sentiment_df.rename(columns={'timestamp': 'Date', 'value': 'Value'}, inplace = True)
    #Format the dates
    sentiment_df['Date'] = pd.to_datetime(sentiment_df["Date"], format = "%m-%d-%Y")
    #Convert value to int, and center the sentiment value at 0
    sentiment_df["Value"] = sentiment_df['Value'].apply(int)
    sentiment_df['Value'] = sentiment_df['Value'] - 50

    #This should really be done with resample but I had a tough time getting it to work that way

    sentiment = np.empty_like(mydata.BTCClose)

    for i, row in mydata.iterrows():
        #Checked that both dfs have pandas timestamp date datatypes
        try:
            sentiment[i] = sentiment_df[sentiment_df.Date == row.Date.floor(freq = 'D')].Value
        except ValueError:
            print('Index: ' + str(i))
            print(sentiment)

            # print("SENTIMENT VECTOR: : ")
            # print(sentiment)
            mydata['Sentiment'] = sentiment


def discrete_derivative(col_name):
    # df['d/dt_' + col_name] = (df[col_name].shift(-1, fill_value = 0) - df[col_name].shift(1, fill_value = 0))/(2*granularity) #this is a centered derivative
    # df['d/dt_' + col_name].iloc[-1] = df[col_name][-2] - df[col_name][-1])/granularity  #Fill in the last value
    df['d/dt_' + col_name] = (df[col_name] - df[col_name].shift(1))/granularity  #I used a non centered derivative because in real time this is the best we can do


def sign_mapping(df):
    #Loop to feature map
    for i, col in enumerate(df.columns):
        if col[3:7] not in ['Open', 'High', 'Low']:
            new_name = col + '-sign'
            df[new_name] = 0
            df[new_name].loc[df[col] - df[col].shift(1) > 0] = 1
    # print(df.head())


def time_of_day(df):
    "Adds the time of day as a column"
    df['Time of Day'] = [date.hour for date in df.index]
    return df


def stack(n, df):
    # This function stacks the states so that both the current state and previous n states are passed.
    new_df = df.copy()
    for i in range(n):
        shifted_df = df.shift(i)
        new_cols = [c + "_shift_" + str(i) for c in shifted_df.columns]
        shifted_df.columns = new_cols
        new_df = pd.concat([new_df, shifted_df], axis=1, sort=True)
    return new_df


def build_features(candle_df, markets, feature_dict):
        """This method takes the raw candle data and constructs features based on the provided list of strings"""
        
        print('Constructing features... ', end = ' ')
        
        if feature_dict is None:
            print('no features built.')
            return candle_df
        df = candle_df.copy()       # At this higher level, it is safer to construct a new dataframe instead of modifying the one that gets passed.
        #This section constructs engineered features and adds them as columns to the df
        """ If you change the number of indicators in this function, be sure to also change the expected number in the enviroment"""

        # Check for illegal values
        acceptable_feature_names = ['sign', 'OBV', 'EMA', 'MACD', 'RSI', 'sentiment', 'renko', 'time of day', 
                                    'knn', 'mlp', 'ridge', 'stack']
        for f in feature_dict:           # Iterate over the keys
            if not f in acceptable_feature_names:
                print('An unrecognized feature has been passed to the feature contructor (not in the acceptable feature list).')
                raise(ValueError)

        #Add the features to the df. It would be great to have a dict of features and functions but im not sure how to do that
        for market in markets:
            token = market[4:7] #this is something like 'BTC' or 'ETH'
            for feature in feature_dict:               # Iterate over the keys
                if feature == 'sign':
                    sign_mapping(df)
                elif feature == 'OBV':
                    df[token + 'OBV'] = ta.volume.on_balance_volume(df[token + 'Close'], df[token + 'Volume'], fillna  = True)
                    # df[token + 'OBV'] = df[token + 'OBV'] - df[token + 'OBV'].shift(1)
                elif feature == 'MACD':
                    df[token + 'MACD'] = ta.trend.macd_diff(df[token + 'Close'], fillna  = True)
                elif feature == 'RSI':
                    df[token + 'RSI'] = ta.momentum.rsi(df[token + 'Close'], fillna  = True) - 50
                elif feature == 'EMA':
                    for base in feature_dict[feature]:
                        add_EMA_as_column(token, base, df)
                    # add_EMA_as_column(token, int(base*8/3))
                    # add_EMA_as_column(token, int(base*13/3))
                # discrete_derivative('EMA_' + str(base))
                # discrete_derivative('EMA_' + str(int(base*8/3)))
                # discrete_derivative('EMA_' + str(int(base*13/3)))
                elif feature == 'sentiment':
                    add_sentiment(df)
                elif feature == 'renko':
                    block = 50
                    add_renko(block, token)
                elif feature == 'time of day':
                    df = time_of_day(df)
                elif feature == 'stack':
                    n = feature_dict[feature][0]
                    df = stack(n, df)
        print('done.')

        df_cols = df.columns

        # Strip out open high low close
        for market in markets:
            token = market[4:7]
            for col in df_cols:
                if col in [token + 'Open', token + 'High', token + 'Low']:
                    df.drop(columns=[col], inplace = True)

        return df