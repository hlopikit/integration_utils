### Самое важное про datetime и timezone и time:
https://it-solution.kdb24.ru/article/73541/

### Чтобы работало как arrow.get
```python
DtIts.get('2013-05-11T21:23:58.970460+07:00')
<DtIts [2013-05-11T21:23:58.970460+07:00]>
```

### Можно dt_its воспользоваться и обрабатывает None
```python
dt_its('2013-05-11T21:23:58.970460+07:00')
<DtIts [2013-05-11T21:23:58.970460+07:00]>
```
```python
dt_its(None)
None
```

### Текущее дата и время
```python
now = DtIts.now()
```

### Смещение времени
```python
after_one_hour = now.shift(hours=1)
```

### Смещение рабочих дней
```python
next_work_day = now.shift_workdays(days=1)
```

### Установка времени установит дате время
```python
time2 = now2.replace(hour=10, minute=10, second=10)
<DtIts [2024-04-27T10:10:10.651603+03:00]>
```

### Дата и время с часовой зоной
```python
DtIts(year=2010, month=1, day=1, tzinfo='Europe/Moscow')
```

### Создание из datetime (timezone ЗАМЕНИТСЯ, а не сдвинется)
```python
DtIts.fromdatetime(datetime.datetime.now(), tzinfo='Europe/Moscow')
```

### Перевод в объект datetime
```python
DtIts.now().datetime
datetime.datetime(2010, 1, 1, 0, 0, tzinfo=tzfile('Europe/Moscow'))
```

### Получение начала и конца дня
```python
start_time = dt.replace(hour=0, minute=0, second=0, microsecond=0)
end_time = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
```

### Начало часа от текущего времени
```python
dt = DtIts.now()
dt = dt.replace(minute=0, second=0, microsecond=0)
```
