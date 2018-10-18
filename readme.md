# PythonOrangeData

Python integration for OrangeData service

Актуальная версия библиотеки: `2.1.1`

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

* получение чека - если произойдёт ошибка получения, будет исключение
```python
order = client.get_order_status(order_id)
```

* создание коррекции
```python
client.create_correction(**correction_kwargs)

# отправка сформированной коррекции
client.post_correction()
```

* получение коррекции - если произойдёт ошибка получения, будет исключение
```python
correction = client.get_correction_status(correction_number)
```