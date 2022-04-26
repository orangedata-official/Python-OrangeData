# PythonOrangeData

Ссылка на сервис: http://orangedata.ru/

Python integration for OrangeData service

Актуальная версия библиотеки: `2.28.2`

##### Использование:
* создать объект класса `OrangeDataClient`
```python
from client import OrangeDataClient

params = {
    'inn': '3123011520',
    'api_url': 'https://apip.orangedata.ru:2443',
    'sign_pkey': 'private_key.pem',
    'client_key': 'client.key',
    'client_cert': 'client.crt',
}

client = OrangeDataClient(**params)
```

* создание чека, добавление сущностей
```python
client.create_order(**order_kwargs)

client.add_position_to_order(**position_to_order_kwargs_1)
client.add_position_to_order(**position_to_order_kwargs_2)

client.add_payment_to_order(**payment_to_order_kwargs)

client.add_agent_to_order(**agent_to_order_kwargs)

client.add_user_attribute(**agent_user_attribute_kwargs)


# отправить сформированный документ
client.send_order()
```

* получение чека
```python
order = client.get_order_status(order_id)
```

* создание коррекции ФФД 1.05
```python
client.create_correction(**correction_kwargs)

# отправка сформированной коррекции
client.post_correction()
```

* получение коррекции
```python
correction = client.get_correction_status(correction_number)
```

* создание коррекции ФФД 1.2
```python
client.create_correction12(**correction_kwargs)

# отправка сформированной коррекции
client.post_correction12()
```
* получение коррекции ФФД 1.2
```python
correction = client.get_correction_status12(correction_number)
```

Методы, которые отправляют данные на апи (send_order, get_order_status, post_correction, get_correction_status и т.д.) 
имеют схожий формат возвращаемых данных:

```python
>>> client.send_order()
{
    'code': 201,
    'data': '',
    'headers': {...}
}
```
* `code` - код ответа от сервера
* `data` - декодированное тело ответа
* `headers` - заголовки ответа
