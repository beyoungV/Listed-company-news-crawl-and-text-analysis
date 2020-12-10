import __init__
import logging
import datetime

from Kite import config
from Kite.database import Database
from Leorio.tokenization import Tokenization

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S')


class GenStockNewsDB(object):

    def __init__(self):
        self.database = Database()
        self.label_range = {3: "3DaysLabel",
                            5: "5DaysLabel",
                            10: "10DaysLabel",
                            15: "15DaysLabel",
                            30: "30DaysLabel",
                            60: "60DaysLabel"}

    def get_all_news_about_specific_stock(self, database_name, collection_name):
        # 获取collection_name的key值，看是否包含RelatedStockCodes，如果没有说明，没有做将新闻中所涉及的
        # 股票代码保存在新的一列
        _keys_list = list(next(self.database.get_collection(database_name, collection_name).find()).keys())
        if "RelatedStockCodes" not in _keys_list:
            tokenization = Tokenization(import_module="jieba", user_dict="./Leorio/financedict.txt")
            tokenization.update_news_database_rows(database_name, collection_name)
        # 创建stock_code为名称的collection
        stock_symbol_list = self.database.get_data("stock", "basic_info", keys=["symbol"])["symbol"].to_list()
        for symbol in stock_symbol_list:
            _collection = self.database.get_collection(config.ALL_NEWS_OF_SPECIFIC_STOCK_DATABASE, symbol)
            _tmp_num_stat = 0
            for row in self.database.get_collection(database_name, collection_name).find():  # 迭代器
                if symbol[2:] in row["RelatedStockCodes"].split(" "):
                    # 返回新闻发布后n天的标签
                    _tmp_dict = {}
                    for label_days, key_name in self.label_range.items():
                        _tmp_dict.update({key_name: self._label_news(
                            datetime.datetime.strptime(row["Date"].split(" ")[0], "%Y-%m-%d"), symbol, label_days)})
                    _data = {"Date": row["Date"],
                             "Url": row["Url"],
                             "Title": row["Title"],
                             "Article": row["Article"],
                             "OriDB": database_name,
                             "OriCOL": collection_name}
                    _data.update(_tmp_dict)
                    _collection.insert_one(_data)
                    _tmp_num_stat += 1
            logging.info("there are {} news mentioned {} in {} collection ... "
                         .format(_tmp_num_stat, symbol, collection_name))

    def _label_news(self, date, symbol, n_days):
        """
        :param date: 类型datetime.datetime，表示新闻发布的日期，只包括年月日，不包括具体时刻，如2020-12-09
        :param symbol: 类型str，表示股票标的，如sh600000
        :param n_days: 类型int，表示根据多少天后的价格设定标签，如新闻发布后n_days天，如果收盘价格上涨，则认为该则新闻是利好消息
        """
        # 计算新闻发布当天经过n_days天后的具体年月日
        new_date = date + datetime.timedelta(days=n_days)
        this_date_data = self.database.get_data(config.STOCK_DATABASE_NAME,
                                                symbol,
                                                query={"date": date}
                                                )
        # 考虑情况：新闻发布日期是非交易日，因此该日期没有价格数据，则往前寻找，比如新闻发布日期是2020-12-12是星期六，
        # 则考虑2020-12-11日的收盘价作为该新闻发布时的数据
        tmp_date = date
        if not this_date_data:
            i = 1
            while not this_date_data:
                tmp_date -= datetime.timedelta(days=i)
                this_date_data = self.database.get_data(config.STOCK_DATABASE_NAME,
                                                        symbol,
                                                        query={"date": tmp_date}
                                                        )
                i += 1
        close_price_this_date = this_date_data["close"][0]

        # 考虑情况：新闻发布后n_days天是非交易日，或者没有采集到数据，因此向后寻找，如新闻发布日期是2020-12-08，5天
        # 后的日期是2020-12-13是周日，因此将2020-12-14日周一的收盘价作为n_days后的数据
        n_days_later_data = self.database.get_data(config.STOCK_DATABASE_NAME,
                                                   symbol,
                                                   query={"date": new_date}
                                                   )
        if not n_days_later_data:
            i = 1
            while not n_days_later_data:
                new_date = date + datetime.timedelta(days=n_days+i)
                n_days_later_data = self.database.get_data(config.STOCK_DATABASE_NAME,
                                                           symbol,
                                                           query={"date": new_date}
                                                           )
                i += 1
        close_price_n_days_later = n_days_later_data["close"][0]
        if close_price_this_date > close_price_n_days_later:
            return "利好"
        elif close_price_this_date < close_price_n_days_later:
            return "利空"
        else:
            return False






if __name__ == "__main__":
    gen_stock_news_db = GenStockNewsDB()
    gen_stock_news_db.get_all_news_about_specific_stock("finnewshunter", "cnstock")
