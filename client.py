import base64
import json
import re
import urllib.parse
from decimal import Decimal

import requests
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15


class OrangeDataClientException(Exception):
    pass


class OrangeDataClientRequestError(OrangeDataClientException):
    pass


class OrangeDataClientAuthError(Exception):
    pass


class OrangeDataClientValidationError(Exception):
    pass


class OrangeDataClient(object):
    __order_request = None
    __correction_request = None

    def __init__(self, inn, api_url, sign_pkey, client_key, client_cert, ca_cert=None, client_cert_pass=None):
        """
        :param inn:
        :param api_url:
        :param sign_pkey: Path to signing private key or his PEM body
        :param client_key: Path to client private key
        :param client_cert: Path to Client 2SSL Certificate
        :param ca_cert: Path to CA Certificate
        :param client_cert_pass: Password for Client 2SSL Certificate
        """
        self.__inn = inn
        self.__api_url = api_url
        self.__sign_pkey = sign_pkey
        self.__client_key = client_key
        self.__client_cert = client_cert
        self.__ca_cert = ca_cert
        self.__client_cert_pass = client_cert_pass

    def create_order(self, id_, type_, customer_contact, taxation_system, group=None, key=None):
        """
        Создание чека
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :param type_: Признак расчета (Число от 1 до 4):
            1 - Приход
            2 - Возврат прихода
            3 - Расход
            4 - Возврат расхода
        :param customer_contact: Телефон или электронный адрес покупателя (Строка от 1 до 64 символов)
        :param taxation_system: Система налогообложения (Число от 0 до 5):
            0 – Общая, ОСН
            1 – Упрощенная доход, УСН доход
            2 – Упрощенная доход минус расход, УСН доход - расход
            3 – Единый налог на вмененный доход, ЕНВД
            4 – Единый сельскохозяйственный налог, ЕСН
            5 – Патентная система налогообложения, Патент
        :param group: Группа устройств, с помощью которых будет пробит чек (не всегда является обязательным полем)
        :param key: Название ключа который должен быть использован для проверки подпись (Строка от 1 до 32 символов
            либо None)
        :return:
        """
        self.__order_request = dict()
        self.__order_request['id'] = id_
        self.__order_request['inn'] = self.__inn
        self.__order_request['group'] = group if group else 'Main'

        if key:
            self.__order_request['key'] = key

        self.__order_request['content'] = {}

        if type_ in [1, 2, 3, 4]:
            self.__order_request['content']['type'] = type_
        else:
            raise OrangeDataClientValidationError('Incorrect order Type')

        self.__order_request['content']['positions'] = []
        self.__order_request['content']['checkClose'] = {}
        self.__order_request['content']['checkClose']['payments'] = []

        if taxation_system in [0, 1, 2, 3, 4, 5]:
            self.__order_request['content']['checkClose']['taxationSystem'] = taxation_system
        else:
            raise OrangeDataClientValidationError('Incorrect taxationSystem')

        if '@' in customer_contact or re.match('^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', customer_contact):
            self.__order_request['content']['customerContact'] = customer_contact
        else:
            raise OrangeDataClientValidationError('Incorrect customer Contact')

    def add_position_to_order(self, quantity, price, tax, text, payment_method_type=4, payment_subject_type=1):
        """
        Добавление позиций
        :param quantity: Количество предмета расчета
        :param price: Цена за единицу предмета расчета с учетом скидок и наценок
        :param tax: Система налогообложения (Число от 1 до 6):
            1 – ставка НДС 18%
            2 – ставка НДС 10%
            3 – ставка НДС расч. 18/118
            4 – ставка НДС расч. 10/110
            5 – ставка НДС 0%
            6 – НДС не облагается
        :param text: Наименование предмета расчета (Строка до 128 символов)
        :param payment_method_type: Признак способа расчета (Число от 1 до 7 или None. Если передано None,
        то будет отправлено значение 4):
            1 – Предоплата 100%
            2 – Частичная предоплата
            3 – Аванс
            4 – Полный расчет
            5 – Частичный расчет и кредит
            6 – Передача в кредит
            7 – оплата кредита
        :param payment_subject_type: Признак предмета расчета (Число от 1 до 13 или None. Если передано None,
        то будет отправлено значение 1):
            1 – Товар
            2 – Подакцизный товар
            3 – Работа
            4 – Услуга
            5 – Ставка азартной игры
            6 – Выигрыш азартной игры
            7 – Лотерейный билет
            8 – Выигрыш лотереи
            9 – Предоставление РИД
            10 – Платеж
            11 – Агентское вознаграждение
            12 – Составной предмет расчета
            13 – Иной предмет расчета
        :return:
        """
        if isinstance(quantity, (float, int)) and isinstance(price, Decimal) and tax in [1, 2, 3, 4, 5, 6] and len(text) < 129:
            position = dict()
            position['quantity'] = quantity
            position['price'] = float(price)
            position['tax'] = tax
            position['text'] = text
        else:
            raise OrangeDataClientValidationError('Invalid Position Quantity, Price, Tax or Text')

        if payment_method_type in [1, 2, 3, 4, 5, 6, 7] and payment_subject_type in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                                                                     12, 13]:
            position['paymentMethodType'] = payment_method_type
            position['paymentSubjectType'] = payment_subject_type
        else:
            raise OrangeDataClientValidationError('Invalid Position paymentMethodType or paymentSubjectType')

        self.__order_request['content']['positions'].append(position)

    def add_payment_to_order(self, type_, amount):
        """
        Добавление оплаты
        :param type_: Тип оплаты (Число от 1 до 16):
            1 – сумма по чеку наличными, 1031
            2 – сумма по чеку электронными, 1081
            14 – сумма по чеку предоплатой (зачетом аванса и (или) предыдущих платежей), 1215
            15 – сумма по чеку постоплатой (в кредит), 1216
            16 – сумма по чеку (БСО) встречным предоставлением, 1217
        :param amount: Сумма оплаты (Десятичное число с точностью до 2 символов после точки*)
        :return:
        """
        if type_ in [1, 2, 14, 15, 16] and isinstance(amount, Decimal):
            payment = dict()
            payment['type'] = type_
            payment['amount'] = float(amount)
            self.__order_request['content']['checkClose']['payments'].append(payment)
        else:
            raise OrangeDataClientValidationError('Invalid Payment Type or Amount')

    def add_agent_to_order(self, agent_type, pay_TOP, pay_AO, pay_APN, pay_OPN, pay_ON, pay_OA, pay_Op_INN, sup_PN):
        """
        Добавление агента
        :param agent_type: Признак агента, 1057. Битовое поле, где номер бита обозначает, что оказывающий услугу
        покупателю (клиенту) пользователь является (Число от 1 до 127):
            0 – банковский платежный агент
            1 – банковский платежный субагент
            2 – платежный агент
            3 – платежный субагент
            4 – поверенный
            5 – комиссионер
            6 – иной агент
        :param pay_TOP: Телефон оператора перевода, 1075 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :param pay_AO: Операция платежного агента, 1044 (Строка длиной от 1 до 24 символов)
        :param pay_APN: Телефон платежного агента, 1073 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :param pay_OPN: Телефон оператора по приему платежей, 1074 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :param pay_ON: Наименование оператора перевода, 1026 (Строка длиной от 1 до 64 символов)
        :param pay_OA: Адрес оператора перевода, 1005 (Строка длиной от 1 до 244 символов)
        :param pay_Op_INN: ИНН оператора перевода, 1016 (Строка длиной от 10 до 12 символов, формат ЦЦЦЦЦЦЦЦЦЦ)
        :param sup_PN: Телефон поставщика, 1171 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :return:
        """
        if 0 < agent_type < 128:
            self.__order_request['content']['agentType'] = agent_type
        else:
            raise OrangeDataClientValidationError('Invalid agentType')

        for phone in pay_TOP:
            if not re.match(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', phone):
                raise OrangeDataClientValidationError('Invalid paymentTransferOperatorPhoneNumbers')

        if pay_TOP:
            self.__order_request['content']['paymentTransferOperatorPhoneNumbers'] = pay_TOP

        if 0 < len(pay_AO) < 25:
            self.__order_request['content']['paymentAgentOperation'] = pay_AO
        else:
            raise OrangeDataClientValidationError('Invalid paymentAgentOperation')

        for phone in pay_APN:
            if not re.match(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', phone):
                raise OrangeDataClientValidationError('Invalid paymentAgentPhoneNumbers')

        if pay_APN:
            self.__order_request['content']['paymentAgentPhoneNumbers'] = pay_APN

        for phone in pay_OPN:
            if not re.match(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', phone):
                raise OrangeDataClientValidationError('Invalid paymentOperatorPhoneNumbers')

        if pay_OPN:
            self.__order_request['content']['paymentOperatorPhoneNumbers'] = pay_OPN

        if 0 < len(pay_ON) < 65 and 0 < len(pay_OA) < 245 and 9 < len(pay_Op_INN) < 13 and len(pay_Op_INN) != 11:
            self.__order_request['content']['paymentOperatorName'] = pay_ON
            self.__order_request['content']['paymentOperatorAddress'] = pay_OA
            self.__order_request['content']['paymentOperatorINN'] = pay_Op_INN
        else:
            raise OrangeDataClientValidationError(
                'Invalid paymentOperatorName, paymentOperatorAddress or paymentOperatorINN')

        for phone in sup_PN:
            if not re.match(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', phone):
                raise OrangeDataClientValidationError('Invalid supplierPhoneNumbers')

        if sup_PN:
            self.__order_request['content']['supplierPhoneNumbers'] = sup_PN

    def add_user_attribute(self, name, value):
        """
        Добавление дополнительного реквизита пользователя, 1084
        :param name: Наименование дополнительного реквизита пользователя, 1085 (Строка от 1 до 64 символов)
        :param value: Значение дополнительного реквизита пользователя, 1086 (Строка от 1 до 175 символов)
        :return:
        """
        if 0 < len(name) < 65 and 0 < len(value) < 176:
            self.__order_request['content']['additionalUserAttribute'] = dict()
            self.__order_request['content']['additionalUserAttribute']['name'] = name
            self.__order_request['content']['additionalUserAttribute']['value'] = value
        else:
            raise OrangeDataClientValidationError('Sting Name or Value is too long')

    def __sign(self, data):
        key = RSA.import_key(open(self.__sign_pkey).read())
        h = SHA256.new(json.dumps(data).encode())
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode()

    def send_order(self):
        """
        Отправка чека
        :return: кортеж (<успешность операции>, <ответ>)
        """
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Signature': self.__sign(self.__order_request)
        }

        response = requests.post(urllib.parse.urljoin(self.__api_url, '/api/v2/documents/'), json=self.__order_request,
                                 headers=headers, cert=(self.__client_cert, self.__client_key))

        if response.status_code == 201:
            return True
        elif response.status_code == 400:
            raise OrangeDataClientRequestError('Bad request')
        elif response.status_code == 401:
            raise OrangeDataClientAuthError('Unauthorized. Client certificate check is failed')
        elif response.status_code == 409:
            raise OrangeDataClientRequestError('Conflict. Order with same id is already exists in the system.')
        elif response.status_code == 503:
            raise OrangeDataClientRequestError('Server error')
        else:
            raise OrangeDataClientRequestError('Unknown response code.')

    def get_order_status(self, id_):
        """
        Проверка состояния чека
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :return:
        """
        if not (0 < len(id_) < 33):
            raise OrangeDataClientValidationError('Invalid order identifier')

        url = urllib.parse.urljoin(
            self.__api_url,
            '/api/v2/documents/{inn}/status/{document_id}'.format(inn=self.__inn, document_id=id_)
        )

        response = requests.get(url, cert=(self.__client_cert, self.__client_key))

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 202:
            return response.content.decode()
        elif response.status_code == 400:
            raise OrangeDataClientRequestError('Bad request')
        elif response.status_code == 404:
            raise OrangeDataClientRequestError('Not found.')
        elif response.status_code == 401:
            raise OrangeDataClientAuthError('Unauthorized. Client certificate check is failed')
        else:
            raise OrangeDataClientException('Unknown response code.')

    def create_correction(self, id_, correction_type, type_, description, cause_document_date, cause_document_number,
                          total_sum, cash_sum, e_cash_sum, pre_payment_sum, post_payment_sum, other_payment_sum,
                          tax_1_sum, tax_2_sum, tax_3_sum, tax_4_sum, tax_5_sum, tax_6_sum, taxation_system, group=None,
                          key=None):
        """
        Создание чека-коррекции
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :param correction_type: 1173, тип коррекции (Число):
            0 - Самостоятельно
            1 - По предписанию
        :param type_: Признак расчета, 1054 (Число):
            1 - Приход
            3 - Расход
        :param description: 1177, описание коррекции (Строка от 1 до 244 символов)
        :param cause_document_date: 1178, дата документа основания для коррекции В данном реквизите время
        всегда указывать, как 00:00:00 (Время в виде строки в формате ISO8601)
        :param cause_document_number: 1179, номер документа основания для коррекции (Строка от 1 до 32 символов)
        :param total_sum: 1020, сумма расчета, указанного в чеке (БСО) (Десятичное число с точностью до 2
        символов после точки)
        :param cash_sum: 1031, сумма по чеку (БСО) наличными (Десятичное число с точностью до 2 символов после точки)
        :param e_cash_sum: 1081, сумма по чеку (БСО) электронными (Десятичное число с точностью до 2 символов
        после точки)
        :param pre_payment_sum: 1215, сумма по чеку (БСО) предоплатой (зачетом аванса и (или) предыдущих платежей)
        (Десятичное число с точностью до 2 символов после точки)
        :param post_payment_sum: 1216, сумма по чеку (БСО) постоплатой (в кредит) (Десятичное число с точностью до 2
        символов после точки)
        :param other_payment_sum: 1217, сумма по чеку (БСО) встречным предоставлением (Десятичное число с точностью
        до 2 символов после точки)
        :param tax_1_sum: 1102, сумма НДС чека по ставке 18% (Десятичное число с точностью до 2 символов после точки)
        :param tax_2_sum: 1103, сумма НДС чека по ставке 10% (Десятичное число с точностью до 2 символов после точки)
        :param tax_3_sum: 1104, сумма расчета по чеку с НДС по ставке 0% (Десятичное число с точностью до 2 символов
        после точки)
        :param tax_4_sum: 1105, сумма расчета по чеку без НДС (Десятичное число с точностью до 2 символов после точки)
        :param tax_5_sum: 1106, сумма НДС чека по расч. ставке 18/118 (Десятичное число с точностью до 2 символов
        после точки)
        :param tax_6_sum: 1107, сумма НДС чека по расч. ставке 10/110 (Десятичное число с точностью до 2 символов
        после точки)
        :param taxation_system: 1055, применяемая система налогообложения (Число):
            0 - Общая
            1 - Упрощенная доход
            2 - Упрощенная доход минус расход
            3 - Единый налог на вмененный доход
            4 - Единый сельскохозяйственный налог
            5 - Патентная система налогообложения
        :param group: Группа устройств, с помощью которых будет пробит чек (не всегда является обязательным полем)
        :param key: Название ключа который должен быть использован для проверки подпись
        :return:
        """
        self.__correction_request = dict()
        self.__correction_request['id'] = id_
        self.__correction_request['inn'] = self.__inn
        self.__correction_request['group'] = group if group else 'Main'

        if key:
            self.__correction_request['key'] = key

        self.__correction_request['content'] = {}

        if correction_type in [0, 1]:
            self.__correction_request['content']['correctionType'] = correction_type
        else:
            raise OrangeDataClientValidationError('Incorrect correction CorrectionType')

        if type_ in [1, 3]:
            self.__correction_request['content']['type'] = type_
        else:
            raise OrangeDataClientValidationError('Incorrect correction Type')

        self.__correction_request['content']['description'] = description[:244]
        self.__correction_request['content']['causeDocumentDate'] = cause_document_date.isoformat()
        self.__correction_request['content']['causeDocumentNumber'] = cause_document_number
        self.__correction_request['content']['totalSum'] = float(total_sum)
        self.__correction_request['content']['cashSum'] = float(cash_sum)
        self.__correction_request['content']['eCashSum'] = float(e_cash_sum)
        self.__correction_request['content']['prepaymentSum'] = float(pre_payment_sum)
        self.__correction_request['content']['postpaymentSum'] = float(post_payment_sum)
        self.__correction_request['content']['otherPaymentTypeSum'] = float(other_payment_sum)
        self.__correction_request['content']['tax1Sum'] = float(tax_1_sum)
        self.__correction_request['content']['tax2Sum'] = float(tax_2_sum)
        self.__correction_request['content']['tax3Sum'] = float(tax_3_sum)
        self.__correction_request['content']['tax4Sum'] = float(tax_4_sum)
        self.__correction_request['content']['tax5Sum'] = float(tax_5_sum)
        self.__correction_request['content']['tax6Sum'] = float(tax_6_sum)

        if taxation_system in [0, 1, 2, 3, 4, 5]:
            self.__correction_request['content']['taxationSystem'] = taxation_system
        else:
            raise OrangeDataClientValidationError('Incorrect taxationSystem')

    def post_correction(self):
        """
        Отправка чека-коррекции на обработку
        :return:
        """
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Signature': self.__sign(self.__correction_request)
        }

        response = requests.post(urllib.parse.urljoin(self.__api_url, '/api/v2/corrections/'),
                                 json=self.__correction_request, headers=headers,
                                 cert=(self.__client_cert, self.__client_key))

        if response.status_code == 201:
            return True
        elif response.status_code == 400:
            raise OrangeDataClientRequestError('Bad request')
        elif response.status_code == 401:
            raise OrangeDataClientAuthError('Unauthorized. Client certificate check is failed')
        elif response.status_code == 409:
            raise OrangeDataClientRequestError('Conflict. Order with same id is already exists in the system.')
        elif response.status_code == 503:
            raise OrangeDataClientRequestError('Server error')
        else:
            raise OrangeDataClientRequestError('Unknown response code.')

    def get_correction_status(self, id_):
        """
        Проверка состояния чека-коррекции
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :return:
        """
        if not (0 < len(id_) < 33):
            raise OrangeDataClientValidationError('Invalid order identifier')

        url = urllib.parse.urljoin(
            self.__api_url,
            '/api/v2/corrections/{inn}/status/{document_id}'.format(inn=self.__inn, document_id=id_)
        )

        response = requests.get(url, cert=(self.__client_cert, self.__client_key))

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 202:
            return response.content.decode()
        elif response.status_code == 400:
            raise OrangeDataClientRequestError('Bad request')
        elif response.status_code == 404:
            raise OrangeDataClientRequestError('Not found.')
        elif response.status_code == 401:
            raise OrangeDataClientAuthError('Unauthorized. Client certificate check is failed')
        else:
            raise OrangeDataClientException('Unknown response code.')
