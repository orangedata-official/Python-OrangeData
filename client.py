import base64
import json
import re
import urllib.parse
import time
from decimal import Decimal

import requests
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from validators import phone_is_valid, length_is_valid, email_is_valid


class OrangeDataClientValidationError(Exception):
    pass


class OrangeDataClient(object):
    __order_request = None
    __correction_request = None

    def __init__(self, inn, api_url, sign_private_key, client_key, client_cert, ca_cert=None, client_cert_pass=None):
        """
        :param inn:
        :param api_url:
        :param sign_private_key: Path to signing private key or his PEM body
        :param client_key: Path to client private key
        :param client_cert: Path to Client 2SSL Certificate
        :param ca_cert: Path to CA Certificate
        :param client_cert_pass: Password for Client 2SSL Certificate
        """
        self.__inn = inn
        self.__api_url = api_url
        self.__sign_private_key = sign_private_key
        self.__client_key = client_key
        self.__client_cert = client_cert
        self.__ca_cert = ca_cert
        self.__client_cert_pass = client_cert_pass

    def create_order(self, id_, type_, customer_contact, taxation_system, group=None, key=None, ffd_version=2, ignore_item_code_check=0):
        """
        Создание чека
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :param type_: Признак расчета, 1054 (Число от 1 до 4):
            1 - Приход
            2 - Возврат прихода
            3 - Расход
            4 - Возврат расхода
        :param customer_contact: Телефон или электронный адрес покупателя, 1008 (Строка от 1 до 64 символов)
        :param taxation_system: Система налогообложения, 1055 (Число от 0 до 5):
            0 – Общая, ОСН
            1 – Упрощенная доход, УСН доход
            2 – Упрощенная доход минус расход, УСН доход - расход
            3 – Единый налог на вмененный доход, ЕНВД
            4 – Единый сельскохозяйственный налог, ЕСН
            5 – Патентная система налогообложения, Патент
        :param group: Группа устройств, с помощью которых будет пробит чек (не всегда является обязательным полем)
        :param key: Название ключа который должен быть использован для проверки подпись (Строка от 1 до 32 символов
            либо None)
        :param ffd_version: версия ФФД (2 - ФФД1.05, 4 - ФФД1.2)
        :param ignore_item_code_check: Флаг указывающий стоит ли игнорировать проверку КМ. Если флаг не указан, то для формирования чека все КМ долђны успешно пройти проверку:
        в тэге 2106 биты номер 0, 1, 2, 3 имеют состояние «1» Если ђе флаг не указан и КМ не прошел проверку чек не будет сформирован и запрос статуса будет возвращать статус 422 Unprocessable Entity (булево)
        :type id_: str
        :type type_: int
        :type customer_contact: str
        :type taxation_system: int
        :type group: str or None
        :type key: str or None
        :type ffd_version: int
        :type ignore_item_code_check: bool
        :return:
        """
        self.__order_request = dict()
        self.__order_request['id'] = id_
        self.__order_request['inn'] = self.__inn
        if group:
            self.__order_request['group'] = group

        if key:
            self.__order_request['key'] = key

        self.__order_request['ignoreItemCodeCheck'] = ignore_item_code_check
        self.__order_request['content'] = {}

        if ffd_version == 2 or ffd_version == 4:
            self.__order_request['content']['ffdVersion'] = ffd_version
        else:
            raise OrangeDataClientValidationError('Incorrect ffd version')


        if type_ in (1, 2, 3, 4):
            self.__order_request['content']['type'] = type_
        else:
            raise OrangeDataClientValidationError('Incorrect order Type')

        self.__order_request['content']['positions'] = []
        self.__order_request['content']['checkClose'] = {}
        self.__order_request['content']['checkClose']['payments'] = []

        if taxation_system in (0, 1, 2, 3, 4, 5):
            self.__order_request['content']['checkClose']['taxationSystem'] = taxation_system
        else:
            raise OrangeDataClientValidationError('Incorrect taxationSystem')

        if '@' in customer_contact or re.match('^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$', customer_contact):
            self.__order_request['content']['customerContact'] = customer_contact
        else:
            raise OrangeDataClientValidationError('Incorrect customer Contact')

    def add_position_to_order(self, quantity, price, tax, text, payment_method_type=4, payment_subject_type=1,
                              supplier_inn=None, supplier_phone_numbers=None, supplier_name=None, agent_type=None,
                              payment_transfer_operator_phone_numbers=None, payment_agent_operation=None,
                              payment_agent_phone_numbers=None, payment_operator_phone_numbers=None,
                              payment_operator_name=None, payment_operator_address=None, payment_operator_inn=None,
                              unit_of_measurement=None, additional_attribute=None, manufacturer_country_code=None,
                              customs_declaration_number=None, excise=None, tax_sum=None, quantity_measurement_unit=None,
                              item_code=None, planned_status=None, fractional_quantity_numerator=None, fractional_quantity_denominator=None,
                              industry_attribute_foivId=None,  industry_attribute_cause_document_date=None, industry_attribute_cause_document_number=None,
                              industry_attribute_value=None, barcodes_ean8=None, barcodes_ean13=None, barcodes_itf14=None,
                              barcodes_gs1=None, barcodes_mi=None, barcodes_egais20=None, barcodes_egais30=None, barcodes_f1=None,
                              barcodes_f2=None, barcodes_f3=None, barcodes_f4=None, barcodes_f5=None, barcodes_f6=None, unit_tax_sum=None):
        """
        Добавление позиций
        :param quantity: Количество предмета расчета, 1023
        :param price: Цена за единицу предмета расчета с учетом скидок и наценок, 1079
        :param tax: Система налогообложения, 1199 (Число от 1 до 6):
            1 – ставка НДС 20%
            2 – ставка НДС 10%
            3 – ставка НДС расч. 20/120
            4 – ставка НДС расч. 10/110
            5 – ставка НДС 0%
            6 – НДС не облагается
        :param text: Наименование предмета расчета, 1030 (Строка до 128 символов)
        :param payment_method_type: Признак способа расчета, 1214 (Число от 1 до 7.
        По умолчанию будет отправлено значение 4):
            1 – Предоплата 100%
            2 – Частичная предоплата
            3 – Аванс
            4 – Полный расчет
            5 – Частичный расчет и кредит
            6 – Передача в кредит
            7 – оплата кредита
        :param payment_subject_type: Признак предмета расчета, 1212 (Число от 1 до 13.
        По умолчанию будет отправлено значение 1):
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
        :param supplier_inn: ИНН поставщика, 1226 (Строка длиной от 10 до 12 символов, формат ЦЦЦЦЦЦЦЦЦЦ)
        :param supplier_phone_numbers: Телефон поставщика, 1171 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :param supplier_name: Наименование поставщика, 1225 (Строка до 239 символов. Внимание: в данные 239
        символа включаются телефоны поставщика + 4 символа на каждый телефон. Например, если передано 2 телефона
        поставщика длиной 12 и 14 символов, то максимальная длина наименования поставщика будет
        239 – (12 + 4) – (14 + 4)  = 205 символов)
        :param agent_type: Признак агента, 1222. Число. Оказывающий услугу покупателю (клиенту) пользователь является:
            0 – банковский платежный агент
            1 – банковский платежный субагент
            2 – платежный агент
            3 – платежный субагент
            4 – поверенный
            5 – комиссионер
            6 – иной агент
        :param payment_transfer_operator_phone_numbers: Телефон оператора перевода, 1075 (Массив строк длиной
        от 1 до 19 символов, формат +{Ц})
        :param payment_agent_operation: Операция платежного агента, 1044 (Строка длиной от 1 до 24 символов)
        :param payment_agent_phone_numbers: Телефон платежного агента, 1073 (Массив строк длиной от 1 до 19 символов,
        формат +{Ц})
        :param payment_operator_phone_numbers: Телефон оператора по приему платежей, 1074 (Массив строк длиной
        от 1 до 19 символов, формат +{Ц}, необязательное поле)
        :param payment_operator_name: Наименование оператора перевода, 1026 (Строка длиной от 1 до 64 символов)
        :param payment_operator_address: Адрес оператора перевода, 1005
        :param payment_operator_inn: ИНН оператора перевода, 1016 (Строка длиной от 10 до 12 символов,
        формат ЦЦЦЦЦЦЦЦЦЦ, необязательное поле)
        :param unit_of_measurement: Единица измерения предмета расчёта, 1197 (Строка длиной от 1 до 16 символов)
        :param additional_attribute: Дополнительный реквизит предмета расчета, 1191 (Строка от 1 до 64 символов)
        :param manufacturer_country_code: Код страны происхождения товара, 1230 (Строка длиной от 1 до 3 символов,
        формат ЦЦЦ. Сервис автоматически дополнит строку до 3 символов пробелами.)
        :param customs_declaration_number: Номер таможенной декларации, 1231 (Строка от 1 до 32 символов)
        :param excise: Акциз, 1229 (Десятичное число с точностью до 2 символов после точки)
        :param tax_sum: Сумма НДС за предмет расчета, 1200 (Десятичное число с точностью до 2 символов после точки.)
        :param quantity_measurement_unit: Мера количества предмета расчета, 2108 (Число от 0 до 255, если не указан – 0. Поддерживается только ФФД1.2)
        :param item_code: Код маркировки, 2000 (Строка от 1 до 223 символов. Поддерживается только ФФД1.2)
        :param planned_status: Планируемый статус, 2003 (Число от 0 до 256. Поддерживается только ФФД1.2)
        :param fractional_quantity_numerator: Дробное количество маркированного товара - Числитель, 1293 (Целое беззнаковое число 8 байт. Поддерживается только ФФД1.2)
        :param fractional_quantity_denominator: Дробное количество маркированного товара - Знаменатель, 1294 (Целое беззнаковое число 8 байт. Поддерживается только ФФД1.2)
        :param industry_attribute_foivId: Отраслевой реквизит предмета расчета - Идентификатор ФОИВ, 1262  (Строка от 1 до 3 символов. Поддерживается только ФФД1.2)
        :param industry_attribute_cause_document_date: Отраслевой реквизит предмета расчета - Дата документа основания, 1263 (Строка 10 символов, формат ДД.ММ.ГГГГ. Поддерживается только ФФД1.2)
        :param industry_attribute_cause_document_number: Отраслевой реквизит предмета расчета - Номер документа основания, 1264 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param industry_attribute_value: Отраслевой реквизит предмета расчета - Значение отраслевого реквизита, 1265 (Строка от 1 до 239 символов. Поддерживается только ФФД1.2)
        :param barcodes_ean8: Штрих-коды предмета расчета - КТ EAN-8, 1301 (Строка 8 символов. Поддерживается только ФФД1.2)
        :param barcodes_ean13: Штрих-коды предмета расчета - КТ EAN-13, 1302 (Строка 13 символов. Поддерживается только ФФД1.2)
        :param barcodes_itf14:  Штрих-коды предмета расчета - КТ ITF-14, 1303 (Строка 14 символов. Поддерживается только ФФД1.2)
        :param barcodes_gs1: Штрих-коды предмета расчета -КТ GS1.0, 1304 (Строка от 1 до 38 символов. Поддерживается только ФФД1.2)
        :param barcodes_mi: Штрих-коды предмета расчета - КТ МИ, 1307 (Строка 20 символов. Поддерживается только ФФД1.2)
        :param barcodes_egais20: Штрих-коды предмета расчета - КТ ЕГАИС-2.0, 1308 (Строка 23 символа. Поддерживается только ФФД1.2)
        :param barcodes_egais30: Штрих-коды предмета расчета - КТ ЕГАИС-3.0, 1309 (Строка 14 символов. Поддерживается только ФФД1.2)
        :param barcodes_f1: Штрих-коды предмета расчета - КТ Ф.1, 1320 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f2: Штрих-коды предмета расчета - КТ Ф.2, 1321 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f3: Штрих-коды предмета расчета - КТ Ф.3, 1322 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f4: Штрих-коды предмета расчета - КТ Ф.4, 1323 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f5: Штрих-коды предмета расчета - КТ Ф.5, 1324 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f6: Штрих-коды предмета расчета - КТ Ф.6, 1325 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param unit_tax_sum: Размер НДС за единицу предмета расчета, 1198 (Десятичное число с точностью до 2 символов после точки)
        :type quantity: float or int
        :type price: Decimal
        :type tax: int
        :type text: str
        :type payment_method_type: int
        :type payment_subject_type: int
        :type supplier_inn: str
        :type supplier_phone_numbers: list
        :type supplier_name: str
        :type agent_type: int
        :type payment_transfer_operator_phone_numbers: list
        :type payment_agent_operation: str
        :type payment_agent_phone_numbers: list
        :type payment_operator_phone_numbers: list
        :type payment_operator_name: str
        :type payment_operator_address: str
        :type payment_operator_inn: str
        :type unit_of_measurement: str
        :type additional_attribute: str
        :type manufacturer_country_code: str
        :type customs_declaration_number: str
        :type excise: int or float
        :type tax_sum: int or float
        :type quantity_measurement_unit: int
        :type item_code: str
        :type planned_status: int
        :type fractional_quantity_numerator: int
        :type fractional_quantity_denominator: int
        :type industry_attribute_foivId: str
        :type industry_attribute_cause_document_date: str
        :type industry_attribute_cause_document_number: str
        :type industry_attribute_value: str
        :type barcodes_ean8: str
        :type barcodes_ean13: str
        :type barcodes_itf14: str
        :type barcodes_gs1: str
        :type barcodes_mi: str
        :type barcodes_egais20: str
        :type barcodes_egais30: str
        :type barcodes_f1: str
        :type barcodes_f2: str
        :type barcodes_f3: str
        :type barcodes_f4: str
        :type barcodes_f5: str
        :type barcodes_f6: str
        :type unit_tax_sum: int or float
        :return:
        """
        if isinstance(quantity, (float, int)) and isinstance(price, Decimal) and tax in (
                1, 2, 3, 4, 5, 6) and length_is_valid(text, max_=128):
            position = dict()
            position['quantity'] = quantity
            position['price'] = float(price)
            position['tax'] = tax
            position['text'] = text
        else:
            raise OrangeDataClientValidationError('Invalid Position Quantity, Price, Tax or Text')

        if payment_method_type in (1, 2, 3, 4, 5, 6, 7) and payment_subject_type in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                                                                     12, 13):
            position['paymentMethodType'] = payment_method_type
            position['paymentSubjectType'] = payment_subject_type
        else:
            raise OrangeDataClientValidationError('Invalid Position payment_method_type or payment_subject_type')

        if supplier_inn:
            if length_is_valid(supplier_inn, 10, 13):
                position['supplierINN'] = supplier_inn

        if supplier_phone_numbers or supplier_name:
            position['supplierInfo'] = {}

        if supplier_phone_numbers:
            for phone in supplier_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid supplier_phone_numbers')

                position['supplierInfo']['phoneNumbers'] = supplier_phone_numbers

        if supplier_name:
            # В данные 239 символа включаются телефоны поставщика + 4 символа на каждый телефон.
            # Например, если передано 2 телефона поставщика длиной 12 и 14 символов,
            # то максимальная длина наименования поставщика будет 239 – (12 + 4) – (14 + 4)  = 205 символов
            max_length = 239 - (len(''.join(position['supplierInfo'].get('phoneNumbers', []))) + 4 * len(
                position['supplierInfo'].get('phoneNumbers', [])))

            if length_is_valid(supplier_name, 1, max_length):
                position['supplierInfo']['name'] = supplier_name
            else:
                raise OrangeDataClientValidationError('Invalid supplier name')

        if agent_type:
            agent_type = 2 ** agent_type

            if 0 < agent_type < 128:
                position['agentType'] = agent_type
            else:
                raise OrangeDataClientValidationError('Invalid agent_type')

        if payment_transfer_operator_phone_numbers or payment_agent_operation \
                or payment_transfer_operator_phone_numbers or payment_operator_name \
                or payment_operator_address or payment_operator_inn:
            position['agentInfo'] = {}

        if payment_transfer_operator_phone_numbers:
            for phone in payment_transfer_operator_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid payment_transfer_operator_phone_numbers')

                position['agentInfo']['paymentTransferOperatorPhoneNumbers'] = payment_transfer_operator_phone_numbers

        if payment_agent_operation:
            if length_is_valid(payment_agent_operation, 1, 24):
                position['agentInfo']['paymentAgentOperation'] = payment_agent_operation
            else:
                raise OrangeDataClientValidationError('Invalid payment_agent_operation')

        if payment_agent_phone_numbers:
            for phone in payment_agent_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid payment_agent_phone_numbers')

                position['agentInfo']['paymentAgentPhoneNumbers'] = payment_agent_phone_numbers

        if payment_operator_phone_numbers:
            for phone in payment_operator_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid payment_operator_phone_numbers')

                position['agentInfo']['paymentOperatorPhoneNumbers'] = payment_operator_phone_numbers

        if payment_operator_name:
            if length_is_valid(payment_operator_name, 1, 64):
                position['agentInfo']['paymentOperatorName'] = payment_operator_name
            else:
                raise OrangeDataClientValidationError('Invalid payment_operator_name')

        if payment_operator_address:
            if length_is_valid(payment_operator_address, 1, 243):
                position['agentInfo']['paymentOperatorAddress'] = payment_operator_address
            else:
                raise OrangeDataClientValidationError('Invalid payment_operator_address')

        if payment_operator_inn:
            if length_is_valid(payment_operator_inn, 10, 12):
                position['agentInfo']['paymentOperatorINN'] = payment_operator_inn
            else:
                raise OrangeDataClientValidationError('Invalid payment_operator_inn')

        if additional_attribute:
            if length_is_valid(additional_attribute, 1, 64):
                position['additionalAttribute'] = additional_attribute
            else:
                raise OrangeDataClientValidationError('Invalid additional_attribute')

        if manufacturer_country_code:
            if length_is_valid(manufacturer_country_code, 1, 3):
                position['manufacturerCountryCode'] = manufacturer_country_code
            else:
                raise OrangeDataClientValidationError('Invalid additional_attribute')

        if customs_declaration_number:
            if length_is_valid(customs_declaration_number, 1, 32):
                position['customsDeclarationNumber'] = customs_declaration_number
            else:
                raise OrangeDataClientValidationError('Invalid customs_declaration_number')

        if excise:
            if isinstance(excise, (int, float)):
                position['excise'] = excise
            else:
                raise OrangeDataClientValidationError('Invalid excise')

        if tax_sum:
            if isinstance(tax_sum, (int, float)):
                position['taxSum'] = tax_sum
            else:
                raise OrangeDataClientValidationError('Invalid tax_sum')

        if unit_tax_sum:
            if isinstance(unit_tax_sum, (int, float)):
                position['unitTaxSum'] = tax_sum
            else:
                raise OrangeDataClientValidationError('Invalid unit_tax_sum')

        if self.__order_request['content']['ffdVersion'] == 2:  # FFD1.05
            if unit_of_measurement:
                if length_is_valid(unit_of_measurement, 1, 16):
                    position['unitOfMeasurement'] = unit_of_measurement
                else:
                    raise OrangeDataClientValidationError('Invalid unit_of_measurement')

        if self.__order_request['content']['ffdVersion'] == 4:  # FFD1.2
            if quantity_measurement_unit:
                if 0 <= quantity_measurement_unit < 256:
                    position['quantityMeasurementUnit'] = quantity_measurement_unit
                else:
                    raise OrangeDataClientValidationError('Invalid quantity_measurement_unit')
            if item_code:
                if length_is_valid(item_code, 1, 223):
                    position['itemCode'] = item_code
                else:
                    raise OrangeDataClientValidationError('Invalid item_code')
            if planned_status:
                if 0 < planned_status < 256:
                    position['itemCode'] = planned_status
                else:
                    raise OrangeDataClientValidationError('Invalid planned_status')

            if fractional_quantity_numerator:
                if isinstance(fractional_quantity_numerator, int):
                    position['fractionalQuantity'] = {}
                    position['fractionalQuantity']['Numerator'] = fractional_quantity_numerator
                else:
                    raise OrangeDataClientValidationError('Invalid fractional_quantity_numerator')

            if fractional_quantity_denominator:
                if isinstance(fractional_quantity_denominator, int):
                    position['fractionalQuantity']['Denominator'] = fractional_quantity_denominator
                else:
                    raise OrangeDataClientValidationError('Invalid fractional_quantity_denominator')

            position['industryAttribute'] = {}
            if industry_attribute_foivId:
                if length_is_valid(industry_attribute_foivId, 1, 3):
                    position['industryAttribute']['foivId'] = industry_attribute_foivId
                else:
                    raise OrangeDataClientValidationError('Invalid industry_attribute_foivId')
            if industry_attribute_cause_document_date:
                try:
                    time.strptime(industry_attribute_cause_document_date, "%d.%m.%Y")
                    position['industryAttribute']['causeDocumentDate'] = industry_attribute_cause_document_date
                except ValueError:
                    raise OrangeDataClientValidationError('Invalid industry_attribute_cause_document_date')
            if industry_attribute_cause_document_number:
                if length_is_valid(industry_attribute_cause_document_number, 1, 32):
                    position['industryAttribute']['causeDocumentNumber'] = industry_attribute_cause_document_number
                else:
                    raise OrangeDataClientValidationError('Invalid industry_attribute_cause_document_number')
            if industry_attribute_value:
                if length_is_valid(industry_attribute_value, 1, 32):
                    position['industryAttribute']['value'] = industry_attribute_value
                else:
                    raise OrangeDataClientValidationError('Invalid industry_attribute_value')
            position['barcodes'] = {}
            if barcodes_ean8:
                if len(barcodes_ean8) == 8:
                    position['barcodes']['ean8'] = barcodes_ean8
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_ean8')
            if barcodes_ean13:
                if len(barcodes_ean8) == 13:
                    position['barcodes']['ean13'] = barcodes_ean13
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_ean13')
            if barcodes_itf14:
                if len(barcodes_ean8) == 14:
                    position['barcodes']['itf14'] = barcodes_itf14
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_itf14')
            if barcodes_gs1:
                if length_is_valid(barcodes_gs1, 1, 38):
                    position['barcodes']['gs1'] = barcodes_gs1
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_gs1')
            if barcodes_mi:
                if len(barcodes_mi) == 20:
                    position['barcodes']['mi'] = barcodes_mi
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_mi')
            if barcodes_egais20:
                if len(barcodes_egais20) == 23:
                    position['barcodes']['egais20'] = barcodes_egais20
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_egais20')
            if barcodes_egais30:
                if len(barcodes_egais20) == 14:
                    position['barcodes']['egais30'] = barcodes_egais30
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_egais30')
            if barcodes_f1:
                if length_is_valid(barcodes_f1, 1, 32):
                    position['barcodes']['f1'] = barcodes_f1
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_f1')
            if barcodes_f2:
                if length_is_valid(barcodes_f2, 1, 32):
                    position['barcodes']['f2'] = barcodes_f2
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_f2')
            if barcodes_f3:
                if length_is_valid(barcodes_f3, 1, 32):
                    position['barcodes']['f3'] = barcodes_f3
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_f3')
            if barcodes_f4:
                if length_is_valid(barcodes_f4, 1, 32):
                    position['barcodes']['f4'] = barcodes_f4
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_f4')
            if barcodes_f5:
                if length_is_valid(barcodes_f5, 1, 32):
                    position['barcodes']['f5'] = barcodes_f5
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_f5')
            if barcodes_f6:
                if length_is_valid(barcodes_f6, 1, 32):
                    position['barcodes']['f6'] = barcodes_f6
                else:
                    raise OrangeDataClientValidationError('Invalid barcodes_f6')

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
        :param amount: Сумма оплаты, 1020 (Десятичное число с точностью до 2 символов после точки*)
        :type type_: int
        :type amount: Decimal
        :return:
        """
        if type_ in (1, 2, 14, 15, 16) and isinstance(amount, Decimal):
            payment = dict()
            payment['type'] = type_
            payment['amount'] = float(amount)
            self.__order_request['content']['checkClose']['payments'].append(payment)
        else:
            raise OrangeDataClientValidationError('Invalid Payment Type or Amount')

    def add_agent_to_order(self, agent_type=None, pay_TOP=None, pay_AO=None, pay_APN=None, pay_OPN=None, pay_ON=None,
                           pay_OA=None, pay_Op_INN=None, sup_PN=None, automat_number=None, settlement_address=None,
                           settlement_place=None):
        """
        Добавление агента (поддерживается только ФФД 1.05)
        :param agent_type: Признак агента, 1057. Числою Оказывающий услугу покупателю (клиенту) пользователь является:
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
        :param pay_OPN: Телефон оператора по приему платежей, 1074 (Массив строк длиной от 1 до 19 символов,формат +{Ц})
        :param pay_ON: Наименование оператора перевода, 1026 (Строка длиной от 1 до 64 символов)
        :param pay_OA: Адрес оператора перевода, 1005 (Строка длиной от 1 до 244 символов)
        :param pay_Op_INN: ИНН оператора перевода, 1016 (Строка длиной от 10 до 12 символов, формат ЦЦЦЦЦЦЦЦЦЦ)
        :param sup_PN: Телефон поставщика, 1171 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :param automat_number: Номер автомата, 1036 (Строка длиной от 1 до 20 символов)
        :param settlement_address: Адрес расчётов, 1009 (Строка длиной от 1 до 243 символов)
        :param settlement_place: Место расчётов, 1187 (Строка длиной от 1 до 243 символов)
        :type pay_TOP: list
        :type pay_AO: str
        :type pay_APN: list
        :type pay_OPN: list
        :type pay_ON: str
        :type pay_OA: str
        :type pay_Op_INN: str
        :type sup_PN: list
        :type automat_number: str
        :type settlement_address: str
        :type settlement_place: str
        :return:
        """
        if agent_type:
            agent_type = 2 ** agent_type
            if 0 < agent_type < 128:
                self.__order_request['content']['agentType'] = agent_type
            else:
                raise OrangeDataClientValidationError('Invalid agent_type')

        if pay_TOP:
            for phone in pay_TOP:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid pay_TOP')

            self.__order_request['content']['paymentTransferOperatorPhoneNumbers'] = pay_TOP

        if pay_AO:
            if length_is_valid(pay_AO, 1, 24):
                self.__order_request['content']['paymentAgentOperation'] = pay_AO
            else:
                raise OrangeDataClientValidationError('Invalid pay_AO')

        if pay_APN:
            for phone in pay_APN:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid pay_APN')

            self.__order_request['content']['paymentAgentPhoneNumbers'] = pay_APN

        if pay_OPN:
            for phone in pay_OPN:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid pay_OPN')

            self.__order_request['content']['paymentOperatorPhoneNumbers'] = pay_OPN

        if pay_ON:
            if length_is_valid(pay_ON, 1, 64):
                self.__order_request['content']['paymentOperatorName'] = pay_ON
            else:
                raise OrangeDataClientValidationError('Invalid pay_ON')

        if pay_OA:
            if length_is_valid(pay_OA, 1, 243):
                self.__order_request['content']['paymentOperatorAddress'] = pay_OA
            else:
                raise OrangeDataClientValidationError('Invalid pay_OA')

        if pay_Op_INN:
            if length_is_valid(pay_Op_INN, 10, 12):
                self.__order_request['content']['paymentOperatorINN'] = pay_Op_INN
            else:
                raise OrangeDataClientValidationError('Invalid pay_Op_INN')

        if sup_PN:
            for phone in sup_PN:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid sup_PN')

            self.__order_request['content']['supplierPhoneNumbers'] = sup_PN

        if automat_number or settlement_address or settlement_place:
            if length_is_valid(automat_number, 1, 20) and length_is_valid(settlement_address, 1, 243) \
                    and length_is_valid(settlement_place, 1, 243):
                self.__order_request['content']['automatNumber'] = automat_number
                self.__order_request['content']['settlementAddress'] = settlement_address
                self.__order_request['content']['settlementPlace'] = settlement_place
            else:
                raise OrangeDataClientValidationError(
                    'Invalid automat_number or settlement_address or settlement_place')

    def add_user_attribute(self, name, value):
        """
        Добавление дополнительного реквизита пользователя, 1084
        :param name: Наименование дополнительного реквизита пользователя, 1085 (Строка от 1 до 64 символов)
        :param value: Значение дополнительного реквизита пользователя, 1086 (Строка от 1 до 175 символов)
        :type name: str
        :type value: str
        :return:
        """
        self.__order_request['content']['additionalUserAttribute'] = dict()

        if length_is_valid(name, 1, 64):
            self.__order_request['content']['additionalUserAttribute']['name'] = name
        else:
            raise OrangeDataClientValidationError('String name is too long')

        if length_is_valid(value + name, 1, 234):
            self.__order_request['content']['additionalUserAttribute']['value'] = value
        else:
            raise OrangeDataClientValidationError('String name + value is too long')

    def __sign(self, data):
        key = RSA.import_key(open(self.__sign_private_key).read())
        h = SHA256.new(json.dumps(data).encode())
        signature = pkcs1_15.new(key).sign(h)
        return base64.b64encode(signature).decode()

    def send_order(self):
        """
        Отправка чека
        """
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Signature': self.__sign(self.__order_request)
        }

        response = requests.post(urllib.parse.urljoin(self.__api_url, '/api/v2/documents/'), json=self.__order_request,
                                 headers=headers, cert=(self.__client_cert, self.__client_key))

        return self.__create_response(response)

    def get_order_status(self, id_):
        """
        Проверка состояния чека
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :type id_: str
        :return:
        """
        if not length_is_valid(id_, 1, 32):
            raise OrangeDataClientValidationError('Invalid order identifier')

        url = urllib.parse.urljoin(
            self.__api_url,
            '/api/v2/documents/{inn}/status/{document_id}'.format(inn=self.__inn, document_id=id_)
        )

        response = requests.get(url, cert=(self.__client_cert, self.__client_key))

        return self.__create_response(response)

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
        :param tax_1_sum: 1102, сумма НДС чека по ставке 20% (Десятичное число с точностью до 2 символов после точки)
        :param tax_2_sum: 1103, сумма НДС чека по ставке 10% (Десятичное число с точностью до 2 символов после точки)
        :param tax_3_sum: 1104, сумма расчета по чеку с НДС по ставке 0% (Десятичное число с точностью до 2 символов
        после точки)
        :param tax_4_sum: 1105, сумма расчета по чеку без НДС (Десятичное число с точностью до 2 символов после точки)
        :param tax_5_sum: 1106, сумма НДС чека по расч. ставке 20/120 (Десятичное число с точностью до 2 символов
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
        :type id_: str
        :type correction_type: int
        :type type_: int
        :type description: str
        :type cause_document_date: datetime.datetime
        :type cause_document_number: str
        :type total_sum:  float or int or Decimal
        :type cash_sum: float or int or Decimal
        :type e_cash_sum: float or int or Decimal
        :type pre_payment_sum: float or int or Decimal
        :type post_payment_sum: float or int or Decimal
        :type other_payment_sum: float or int or Decimal
        :type tax_1_sum: float or int or Decimal
        :type tax_2_sum: float or int or Decimal
        :type tax_3_sum: float or int or Decimal
        :type tax_4_sum: float or int or Decimal
        :type tax_5_sum: float or int or Decimal
        :type tax_6_sum: float or int or Decimal
        :type taxation_system: int
        :type group: str
        :type key: str
        :return:
        """
        self.__correction_request = dict()
        self.__correction_request['id'] = id_
        self.__correction_request['inn'] = self.__inn
        self.__correction_request['group'] = group if group else 'Main'

        if key:
            self.__correction_request['key'] = key

        self.__correction_request['content'] = {}

        if correction_type in (0, 1):
            self.__correction_request['content']['correctionType'] = correction_type
        else:
            raise OrangeDataClientValidationError('Incorrect correction correction_type')

        if type_ in (1, 3):
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

        if taxation_system in (0, 1, 2, 3, 4, 5):
            self.__correction_request['content']['taxationSystem'] = taxation_system
        else:
            raise OrangeDataClientValidationError('Incorrect taxation_system')

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

        return self.__create_response(response)

    def get_correction_status(self, id_):
        """
        Проверка состояния чека-коррекции
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :type id_: str
        :return:
        """
        if not length_is_valid(id_, 1, 32):
            raise OrangeDataClientValidationError('Invalid order identifier')

        url = urllib.parse.urljoin(
            self.__api_url,
            '/api/v2/corrections/{inn}/status/{document_id}'.format(inn=self.__inn, document_id=id_)
        )

        response = requests.get(url, cert=(self.__client_cert, self.__client_key))

        return self.__create_response(response)

    def create_correction12(self, id_, correction_type, type_, cause_document_date, cause_document_number,
                          total_sum, customer_contact, vat_1_sum, vat_2_sum, vat_3_sum, vat_4_sum, vat_5_sum, vat_6_sum,
                          group=None, key=None, ignore_item_code_check=0):
        """
        Создание чека-коррекции для ФФД1.2
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :param correction_type: 1173, тип коррекции (Число):
            0 - Самостоятельно
            1 - По предписанию
        :param type_: Признак расчета, 1054 (Число):
            1 - Приход
            3 - Расход
        :param cause_document_date: 1178, дата документа основания для коррекции В данном реквизите время
        всегда указывать, как 00:00:00 (Время в виде строки в формате ISO8601)
        :param cause_document_number: 1179, номер документа основания для коррекции (Строка от 1 до 32 символов)
        :param total_sum: 1020, сумма расчета, указанного в чеке (БСО) (Десятичное число с точностью до 2
        символов после точки)
        :param customer_contact: телефон или электронный адрес покупателя, 1008 (Строка от 1 до 64 символов, формат +{Ц} или {С}@{C})
        :param vat_1_sum: 1102, сумма НДС чека по ставке 20% (Десятичное число с точностью до 2 символов после точки)
        :param vat_2_sum: 1103, сумма НДС чека по ставке 10% (Десятичное число с точностью до 2 символов после точки)
        :param vat_3_sum: 1104, сумма расчета по чеку с НДС по ставке 0% (Десятичное число с точностью до 2 символов
        после точки)
        :param vat_4_sum: 1105, сумма расчета по чеку без НДС (Десятичное число с точностью до 2 символов после точки)
        :param vat_5_sum: 1106, сумма НДС чека по расч. ставке 20/120 (Десятичное число с точностью до 2 символов
        после точки)
        :param vat_6_sum: 1107, сумма НДС чека по расч. ставке 10/110 (Десятичное число с точностью до 2 символов
        после точки)
        :param group: Группа устройств, с помощью которых будет пробит чек (не всегда является обязательным полем)
        :param key: Название ключа который должен быть использован для проверки подпись
        :param ignore_item_code_check: Флаг указывающий стоит ли игнорировать проверку КМ.
        Если флаг не указан, то для формирования чека все КМ долђны успешно пройти проверку: в тэге 2106 биты номер 0, 1, 2, 3 имеют состояние «1» Если ђе флаг не указан и КМ не прошел проверку чек не будет сформирован и запрос статуса будет возвращать статус 422 Unprocessable Entity
        :type id_: str
        :type correction_type: int
        :type type_: int
        :type cause_document_date: datetime.datetime
        :type cause_document_number: str
        :type total_sum:  float or int or Decimal
        :type customer_contact: str
        :type vat_1_sum: float or int or Decimal
        :type vat_2_sum: float or int or Decimal
        :type vat_3_sum: float or int or Decimal
        :type vat_4_sum: float or int or Decimal
        :type vat_5_sum: float or int or Decimal
        :type vat_6_sum: float or int or Decimal
        :type group: str
        :type key: str
        :type ignore_item_code_check: bool
        :return:
        """
        self.__correction_request = dict()
        self.__correction_request['id'] = id_
        self.__correction_request['inn'] = self.__inn
        self.__correction_request['group'] = group if group else 'Main_2'
        self.__correction_request['ignoreItemCodeCheck'] = ignore_item_code_check

        if key:
            self.__correction_request['key'] = key

        self.__correction_request['content'] = {}

        self.__correction_request['content']['positions'] = []
        self.__correction_request['content']['checkClose'] = {}
        self.__correction_request['content']['checkClose']['payments'] = []

        if correction_type in (0, 1):
            self.__correction_request['content']['correctionType'] = correction_type
        else:
            raise OrangeDataClientValidationError('Incorrect correction correction_type')

        if type_ in (1, 3):
            self.__correction_request['content']['type'] = type_
        else:
            raise OrangeDataClientValidationError('Incorrect correction Type')

        if phone_is_valid(customer_contact) or email_is_valid(customer_contact):
            self.__correction_request['content']['customerContact'] = customer_contact
        else:
            raise OrangeDataClientValidationError('Incorrect correction customer_contact')

        self.__correction_request['content']['ffdVersion'] = 4
        self.__correction_request['content']['causeDocumentDate'] = cause_document_date.isoformat()
        self.__correction_request['content']['causeDocumentNumber'] = cause_document_number
        self.__correction_request['content']['totalSum'] = float(total_sum)
        self.__correction_request['content']['vat1Sum'] = float(vat_1_sum)
        self.__correction_request['content']['vat2Sum'] = float(vat_2_sum)
        self.__correction_request['content']['vat3Sum'] = float(vat_3_sum)
        self.__correction_request['content']['vat4Sum'] = float(vat_4_sum)
        self.__correction_request['content']['vat5Sum'] = float(vat_5_sum)
        self.__correction_request['content']['vat6Sum'] = float(vat_6_sum)

    def post_correction12(self):
        """
        Отправка чека-коррекции на обработку
        :return:
        """
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Signature': self.__sign(self.__correction_request)
        }

        response = requests.post(urllib.parse.urljoin(self.__api_url, '/api/v2/correction12/'),
                                 json=self.__correction_request, headers=headers,
                                 cert=(self.__client_cert, self.__client_key))

        return self.__create_response(response)

    def add_position_to_correction(self, quantity, price, tax, text, payment_method_type=4, payment_subject_type=1,
                              supplier_inn=None, supplier_phone_numbers=None, supplier_name=None, agent_type=None,
                              payment_transfer_operator_phone_numbers=None, payment_agent_operation=None,
                              payment_agent_phone_numbers=None, payment_operator_phone_numbers=None,
                              payment_operator_name=None, payment_operator_address=None, payment_operator_inn=None,
                              additional_attribute=None, manufacturer_country_code=None,
                              customs_declaration_number=None, excise=None, tax_sum=None, quantity_measurement_unit=None,
                              item_code=None, planned_status=None, fractional_quantity_numerator=None, fractional_quantity_denominator=None,
                              industry_attribute_foivId=None,  industry_attribute_cause_document_date=None, industry_attribute_cause_document_number=None,
                              industry_attribute_value=None, barcodes_ean8=None, barcodes_ean13=None, barcodes_itf14=None,
                              barcodes_gs1=None, barcodes_mi=None, barcodes_egais20=None, barcodes_egais30=None, barcodes_f1=None,
                              barcodes_f2=None, barcodes_f3=None, barcodes_f4=None, barcodes_f5=None, barcodes_f6=None, unit_tax_sum=None):
        """
        Добавление позиций
        :param quantity: Количество предмета расчета, 1023
        :param price: Цена за единицу предмета расчета с учетом скидок и наценок, 1079
        :param tax: Система налогообложения, 1199 (Число от 1 до 6):
            1 – ставка НДС 20%
            2 – ставка НДС 10%
            3 – ставка НДС расч. 20/120
            4 – ставка НДС расч. 10/110
            5 – ставка НДС 0%
            6 – НДС не облагается
        :param text: Наименование предмета расчета, 1030 (Строка до 128 символов)
        :param payment_method_type: Признак способа расчета, 1214 (Число от 1 до 7.
        По умолчанию будет отправлено значение 4):
            1 – Предоплата 100%
            2 – Частичная предоплата
            3 – Аванс
            4 – Полный расчет
            5 – Частичный расчет и кредит
            6 – Передача в кредит
            7 – оплата кредита
        :param payment_subject_type: Признак предмета расчета, 1212 (Число от 1 до 13.
        По умолчанию будет отправлено значение 1):
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
        :param supplier_inn: ИНН поставщика, 1226 (Строка длиной от 10 до 12 символов, формат ЦЦЦЦЦЦЦЦЦЦ)
        :param supplier_phone_numbers: Телефон поставщика, 1171 (Массив строк длиной от 1 до 19 символов, формат +{Ц})
        :param supplier_name: Наименование поставщика, 1225 (Строка до 239 символов. Внимание: в данные 239
        символа включаются телефоны поставщика + 4 символа на каждый телефон. Например, если передано 2 телефона
        поставщика длиной 12 и 14 символов, то максимальная длина наименования поставщика будет
        239 – (12 + 4) – (14 + 4)  = 205 символов)
        :param agent_type: Признак агента, 1222. Число. Оказывающий услугу покупателю (клиенту) пользователь является:
            0 – банковский платежный агент
            1 – банковский платежный субагент
            2 – платежный агент
            3 – платежный субагент
            4 – поверенный
            5 – комиссионер
            6 – иной агент
        :param payment_transfer_operator_phone_numbers: Телефон оператора перевода, 1075 (Массив строк длиной
        от 1 до 19 символов, формат +{Ц})
        :param payment_agent_operation: Операция платежного агента, 1044 (Строка длиной от 1 до 24 символов)
        :param payment_agent_phone_numbers: Телефон платежного агента, 1073 (Массив строк длиной от 1 до 19 символов,
        формат +{Ц})
        :param payment_operator_phone_numbers: Телефон оператора по приему платежей, 1074 (Массив строк длиной
        от 1 до 19 символов, формат +{Ц}, необязательное поле)
        :param payment_operator_name: Наименование оператора перевода, 1026 (Строка длиной от 1 до 64 символов)
        :param payment_operator_address: Адрес оператора перевода, 1005
        :param payment_operator_inn: ИНН оператора перевода, 1016 (Строка длиной от 10 до 12 символов,
        формат ЦЦЦЦЦЦЦЦЦЦ, необязательное поле)
        :param additional_attribute: Дополнительный реквизит предмета расчета, 1191 (Строка от 1 до 64 символов)
        :param manufacturer_country_code: Код страны происхождения товара, 1230 (Строка длиной от 1 до 3 символов,
        формат ЦЦЦ. Сервис автоматически дополнит строку до 3 символов пробелами.)
        :param customs_declaration_number: Номер таможенной декларации, 1231 (Строка от 1 до 32 символов)
        :param excise: Акциз, 1229 (Десятичное число с точностью до 2 символов после точки)
        :param tax_sum: Сумма НДС за предмет расчета, 1200 (Десятичное число с точностью до 2 символов после точки.)
        :param quantity_measurement_unit: Мера количества предмета расчета, 2108 (Число от 0 до 255, если не указан – 0. Поддерживается только ФФД1.2)
        :param item_code: Код маркировки, 2000 (Строка от 1 до 223 символов. Поддерживается только ФФД1.2)
        :param planned_status: Планируемый статус, 2003 (Число от 0 до 256. Поддерживается только ФФД1.2)
        :param fractional_quantity_numerator: Дробное количество маркированного товара - Числитель, 1293 (Целое беззнаковое число 8 байт. Поддерживается только ФФД1.2)
        :param fractional_quantity_denominator: Дробное количество маркированного товара - Знаменатель, 1294 (Целое беззнаковое число 8 байт. Поддерживается только ФФД1.2)
        :param industry_attribute_foivId: Отраслевой реквизит предмета расчета - Идентификатор ФОИВ, 1262  (Строка от 1 до 3 символов. Поддерживается только ФФД1.2)
        :param industry_attribute_cause_document_date: Отраслевой реквизит предмета расчета - Дата документа основания, 1263 (Строка 10 символов, формат ДД.ММ.ГГГГ. Поддерживается только ФФД1.2)
        :param industry_attribute_cause_document_number: Отраслевой реквизит предмета расчета - Номер документа основания, 1264 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param industry_attribute_value: Отраслевой реквизит предмета расчета - Значение отраслевого реквизита, 1265 (Строка от 1 до 239 символов. Поддерживается только ФФД1.2)
        :param barcodes_ean8: Штрих-коды предмета расчета - КТ EAN-8, 1301 (Строка 8 символов. Поддерживается только ФФД1.2)
        :param barcodes_ean13: Штрих-коды предмета расчета - КТ EAN-13, 1302 (Строка 13 символов. Поддерживается только ФФД1.2)
        :param barcodes_itf14:  Штрих-коды предмета расчета - КТ ITF-14, 1303 (Строка 14 символов. Поддерживается только ФФД1.2)
        :param barcodes_gs1: Штрих-коды предмета расчета -КТ GS1.0, 1304 (Строка от 1 до 38 символов. Поддерживается только ФФД1.2)
        :param barcodes_mi: Штрих-коды предмета расчета - КТ МИ, 1307 (Строка 20 символов. Поддерживается только ФФД1.2)
        :param barcodes_egais20: Штрих-коды предмета расчета - КТ ЕГАИС-2.0, 1308 (Строка 23 символа. Поддерживается только ФФД1.2)
        :param barcodes_egais30: Штрих-коды предмета расчета - КТ ЕГАИС-3.0, 1309 (Строка 14 символов. Поддерживается только ФФД1.2)
        :param barcodes_f1: Штрих-коды предмета расчета - КТ Ф.1, 1320 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f2: Штрих-коды предмета расчета - КТ Ф.2, 1321 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f3: Штрих-коды предмета расчета - КТ Ф.3, 1322 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f4: Штрих-коды предмета расчета - КТ Ф.4, 1323 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f5: Штрих-коды предмета расчета - КТ Ф.5, 1324 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param barcodes_f6: Штрих-коды предмета расчета - КТ Ф.6, 1325 (Строка от 1 до 32 символов. Поддерживается только ФФД1.2)
        :param unit_tax_sum: Размер НДС за единицу предмета расчета, 1198 (Десятичное число с точностью до 2 символов после точки)
        :type quantity: float or int
        :type price: Decimal
        :type tax: int
        :type text: str
        :type payment_method_type: int
        :type payment_subject_type: int
        :type supplier_inn: str
        :type supplier_phone_numbers: list
        :type supplier_name: str
        :type agent_type: int
        :type payment_transfer_operator_phone_numbers: list
        :type payment_agent_operation: str
        :type payment_agent_phone_numbers: list
        :type payment_operator_phone_numbers: list
        :type payment_operator_name: str
        :type payment_operator_address: str
        :type payment_operator_inn: str
        :type additional_attribute: str
        :type manufacturer_country_code: str
        :type customs_declaration_number: str
        :type excise: int or float
        :type tax_sum: int or float
        :type quantity_measurement_unit: int
        :type item_code: str
        :type planned_status: int
        :type fractional_quantity_numerator: int
        :type fractional_quantity_denominator: int
        :type industry_attribute_foivId: str
        :type industry_attribute_cause_document_date: str
        :type industry_attribute_cause_document_number: str
        :type industry_attribute_value: str
        :type barcodes_ean8: str
        :type barcodes_ean13: str
        :type barcodes_itf14: str
        :type barcodes_gs1: str
        :type barcodes_mi: str
        :type barcodes_egais20: str
        :type barcodes_egais30: str
        :type barcodes_f1: str
        :type barcodes_f2: str
        :type barcodes_f3: str
        :type barcodes_f4: str
        :type barcodes_f5: str
        :type barcodes_f6: str
        :type unit_tax_sum: int or float
        :return:
        """
        if isinstance(quantity, (float, int)) and isinstance(price, Decimal) and tax in (
                1, 2, 3, 4, 5, 6) and length_is_valid(text, max_=128):
            position = dict()
            position['quantity'] = quantity
            position['price'] = float(price)
            position['tax'] = tax
            position['text'] = text
        else:
            raise OrangeDataClientValidationError('Invalid Position Quantity, Price, Tax or Text')

        if payment_method_type in (1, 2, 3, 4, 5, 6, 7) and payment_subject_type in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
                                                                                     12, 13):
            position['paymentMethodType'] = payment_method_type
            position['paymentSubjectType'] = payment_subject_type
        else:
            raise OrangeDataClientValidationError('Invalid Position payment_method_type or payment_subject_type')

        if supplier_inn:
            if length_is_valid(supplier_inn, 10, 13):
                position['supplierINN'] = supplier_inn

        if supplier_phone_numbers or supplier_name:
            position['supplierInfo'] = {}

        if supplier_phone_numbers:
            for phone in supplier_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid supplier_phone_numbers')

                position['supplierInfo']['phoneNumbers'] = supplier_phone_numbers

        if supplier_name:
            # В данные 239 символа включаются телефоны поставщика + 4 символа на каждый телефон.
            # Например, если передано 2 телефона поставщика длиной 12 и 14 символов,
            # то максимальная длина наименования поставщика будет 239 – (12 + 4) – (14 + 4)  = 205 символов
            max_length = 239 - (len(''.join(position['supplierInfo'].get('phoneNumbers', []))) + 4 * len(
                position['supplierInfo'].get('phoneNumbers', [])))

            if length_is_valid(supplier_name, 1, max_length):
                position['supplierInfo']['name'] = supplier_name
            else:
                raise OrangeDataClientValidationError('Invalid supplier name')

        if agent_type:
            agent_type = 2 ** agent_type

            if 0 < agent_type < 128:
                position['agentType'] = agent_type
            else:
                raise OrangeDataClientValidationError('Invalid agent_type')

        if payment_transfer_operator_phone_numbers or payment_agent_operation \
                or payment_transfer_operator_phone_numbers or payment_operator_name \
                or payment_operator_address or payment_operator_inn:
            position['agentInfo'] = {}

        if payment_transfer_operator_phone_numbers:
            for phone in payment_transfer_operator_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid payment_transfer_operator_phone_numbers')

                position['agentInfo']['paymentTransferOperatorPhoneNumbers'] = payment_transfer_operator_phone_numbers

        if payment_agent_operation:
            if length_is_valid(payment_agent_operation, 1, 24):
                position['agentInfo']['paymentAgentOperation'] = payment_agent_operation
            else:
                raise OrangeDataClientValidationError('Invalid payment_agent_operation')

        if payment_agent_phone_numbers:
            for phone in payment_agent_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid payment_agent_phone_numbers')

                position['agentInfo']['paymentAgentPhoneNumbers'] = payment_agent_phone_numbers

        if payment_operator_phone_numbers:
            for phone in payment_operator_phone_numbers:
                if not phone_is_valid(phone):
                    raise OrangeDataClientValidationError('Invalid payment_operator_phone_numbers')

                position['agentInfo']['paymentOperatorPhoneNumbers'] = payment_operator_phone_numbers

        if payment_operator_name:
            if length_is_valid(payment_operator_name, 1, 64):
                position['agentInfo']['paymentOperatorName'] = payment_operator_name
            else:
                raise OrangeDataClientValidationError('Invalid payment_operator_name')

        if payment_operator_address:
            if length_is_valid(payment_operator_address, 1, 243):
                position['agentInfo']['paymentOperatorAddress'] = payment_operator_address
            else:
                raise OrangeDataClientValidationError('Invalid payment_operator_address')

        if payment_operator_inn:
            if length_is_valid(payment_operator_inn, 10, 12):
                position['agentInfo']['paymentOperatorINN'] = payment_operator_inn
            else:
                raise OrangeDataClientValidationError('Invalid payment_operator_inn')

        if additional_attribute:
            if length_is_valid(additional_attribute, 1, 64):
                position['additionalAttribute'] = additional_attribute
            else:
                raise OrangeDataClientValidationError('Invalid additional_attribute')

        if manufacturer_country_code:
            if length_is_valid(manufacturer_country_code, 1, 3):
                position['manufacturerCountryCode'] = manufacturer_country_code
            else:
                raise OrangeDataClientValidationError('Invalid additional_attribute')

        if customs_declaration_number:
            if length_is_valid(customs_declaration_number, 1, 32):
                position['customsDeclarationNumber'] = customs_declaration_number
            else:
                raise OrangeDataClientValidationError('Invalid customs_declaration_number')

        if excise:
            if isinstance(excise, (int, float)):
                position['excise'] = excise
            else:
                raise OrangeDataClientValidationError('Invalid excise')

        if tax_sum:
            if isinstance(tax_sum, (int, float)):
                position['taxSum'] = tax_sum
            else:
                raise OrangeDataClientValidationError('Invalid tax_sum')

        if unit_tax_sum:
            if isinstance(unit_tax_sum, (int, float)):
                position['unitTaxSum'] = tax_sum
            else:
                raise OrangeDataClientValidationError('Invalid unit_tax_sum')

        if quantity_measurement_unit:
            if 0 <= quantity_measurement_unit < 256:
                position['quantityMeasurementUnit'] = quantity_measurement_unit
            else:
                raise OrangeDataClientValidationError('Invalid quantity_measurement_unit')
        if item_code:
            if length_is_valid(item_code, 1, 223):
                position['itemCode'] = item_code
            else:
                raise OrangeDataClientValidationError('Invalid item_code')
        if planned_status:
            if 0 < planned_status < 256:
                position['itemCode'] = planned_status
            else:
                raise OrangeDataClientValidationError('Invalid planned_status')

        if fractional_quantity_numerator:
            if isinstance(fractional_quantity_numerator, int):
                position['fractionalQuantity'] = {}
                position['fractionalQuantity']['Numerator'] = fractional_quantity_numerator
            else:
                raise OrangeDataClientValidationError('Invalid fractional_quantity_numerator')
        if fractional_quantity_denominator:
            if  isinstance(fractional_quantity_denominator, int):
                position['fractionalQuantity']['Denominator'] = fractional_quantity_denominator
            else:
                raise OrangeDataClientValidationError('Invalid fractional_quantity_denominator')

        position['industryAttribute'] = {}
        if industry_attribute_foivId:
            if length_is_valid(industry_attribute_foivId, 1, 3):
                position['industryAttribute']['foivId'] = industry_attribute_foivId
            else:
                raise OrangeDataClientValidationError('Invalid industry_attribute_foivId')
        if industry_attribute_cause_document_date:
            try:
                time.strptime(industry_attribute_cause_document_date, "%d.%m.%Y")
                position['industryAttribute']['causeDocumentDate'] = industry_attribute_cause_document_date
            except ValueError:
                raise OrangeDataClientValidationError('Invalid industry_attribute_cause_document_date')
        if industry_attribute_cause_document_number:
            if length_is_valid(industry_attribute_cause_document_number, 1, 32):
                position['industryAttribute']['causeDocumentNumber'] = industry_attribute_cause_document_number
            else:
                raise OrangeDataClientValidationError('Invalid industry_attribute_cause_document_number')
        if industry_attribute_value:
            if length_is_valid(industry_attribute_value, 1, 32):
                position['industryAttribute']['value'] = industry_attribute_value
            else:
                raise OrangeDataClientValidationError('Invalid industry_attribute_value')
        position['barcodes'] = {}
        if barcodes_ean8:
            if len(barcodes_ean8) == 8:
                position['barcodes']['ean8'] = barcodes_ean8
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_ean8')
        if barcodes_ean13:
            if len(barcodes_ean8) == 13:
                position['barcodes']['ean13'] = barcodes_ean13
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_ean13')
        if barcodes_itf14:
            if len(barcodes_ean8) == 14:
                position['barcodes']['itf14'] = barcodes_itf14
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_itf14')
        if barcodes_gs1:
            if length_is_valid(barcodes_gs1, 1, 38):
                position['barcodes']['gs1'] = barcodes_gs1
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_gs1')
        if barcodes_mi:
            if len(barcodes_mi) == 20:
                position['barcodes']['mi'] = barcodes_mi
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_mi')
        if barcodes_egais20:
            if len(barcodes_egais20) == 23:
                position['barcodes']['egais20'] = barcodes_egais20
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_egais20')
        if barcodes_egais30:
            if len(barcodes_egais20) == 14:
                position['barcodes']['egais30'] = barcodes_egais30
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_egais30')
        if barcodes_f1:
            if length_is_valid(barcodes_f1, 1, 32):
                position['barcodes']['f1'] = barcodes_f1
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_f1')
        if barcodes_f2:
            if length_is_valid(barcodes_f2, 1, 32):
                position['barcodes']['f2'] = barcodes_f2
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_f2')
        if barcodes_f3:
            if length_is_valid(barcodes_f3, 1, 32):
                position['barcodes']['f3'] = barcodes_f3
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_f3')
        if barcodes_f4:
            if length_is_valid(barcodes_f4, 1, 32):
                position['barcodes']['f4'] = barcodes_f4
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_f4')
        if barcodes_f5:
            if length_is_valid(barcodes_f5, 1, 32):
                position['barcodes']['f5'] = barcodes_f5
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_f5')
        if barcodes_f6:
            if length_is_valid(barcodes_f6, 1, 32):
                position['barcodes']['f6'] = barcodes_f6
            else:
                raise OrangeDataClientValidationError('Invalid barcodes_f6')

        self.__correction_request['content']['positions'].append(position)

    def add_payment_to_correction(self, type_, amount):
        """
        Добавление оплаты
        :param type_: Тип оплаты (Число от 1 до 16):
            1 – сумма по чеку наличными, 1031
            2 – сумма по чеку электронными, 1081
            14 – сумма по чеку предоплатой (зачетом аванса и (или) предыдущих платежей), 1215
            15 – сумма по чеку постоплатой (в кредит), 1216
            16 – сумма по чеку (БСО) встречным предоставлением, 1217
        :param amount: Сумма оплаты, 1020 (Десятичное число с точностью до 2 символов после точки*)
        :type type_: int
        :type amount: Decimal
        :return:
        """
        if type_ in (1, 2, 14, 15, 16) and isinstance(amount, Decimal):
            payment = dict()
            payment['type'] = type_
            payment['amount'] = float(amount)
            self.__correction_request['content']['checkClose']['payments'].append(payment)
        else:
            raise OrangeDataClientValidationError('Invalid Payment Type or Amount')

    def get_correction_status12(self, id_):
        """
        Проверка состояния чека-коррекции ФФД1.2
        :param id_: Идентификатор документа (Строка от 1 до 32 символов)
        :type id_: str
        :return:
        """
        if not length_is_valid(id_, 1, 32):
            raise OrangeDataClientValidationError('Invalid order identifier')

        url = urllib.parse.urljoin(
            self.__api_url,
            '/api/v2/correction12/{inn}/status/{document_id}'.format(inn=self.__inn, document_id=id_)
        )

        response = requests.get(url, cert=(self.__client_cert, self.__client_key))

        return self.__create_response(response)

    @staticmethod
    def __create_response(response):
        """
        :param response: Http-response
        :type response: requests.Response
        :return:
        """
        return {
            'code': response.status_code,
            'data': response.content.decode(),
            'headers': response.headers,
        }
