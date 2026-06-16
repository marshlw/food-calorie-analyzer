import

'dart:io';
import

'dart:convert';
import

'package:flutter/material.dart';
import

'package:image_picker/image_picker.dart';
import

'package:http/http.dart' as http;
import

'package:path_provider/path_provider.dart';

void
main()
{
    runApp(const
MyApp());
}

class MyApp extends StatelessWidget {
const MyApp({super.key});

@ override
Widget build(BuildContext context) {


return MaterialApp(
    title: 'Food Calorie Analyzer',
theme: ThemeData(primarySwatch: Colors.green),
home: const
HomePage(),
);
}
}

class HomePage extends StatefulWidget {
const HomePage({super.key});

@ override
State < HomePage > createState() = > _HomePageState();
}


class _HomePageState extends State < HomePage > {
File? _image;
Map < String, dynamic > ? _result;
bool _isLoading = false;
String? _taskId;
Timer? _pollTimer;

final ImagePicker _picker = ImagePicker();

Future < void > _pickImage(ImageSource source) async {
final XFile? photo = await _picker.pickImage(source: source

);
if (photo != null) {
setState(() {
_image = File(photo.path);
_result = null;
_taskId = null;
});
await _analyzeImage();
}
}

Future < void > _analyzeImage() async {
if (_image == null)
return;

setState(()
{
    _isLoading = true;
_result = null;
});

try {
// 1. Загружаем изображение на сервер
var request = http.MultipartRequest(
'POST',
Uri.parse('http://YOUR_SERVER_IP:8000/api/v1/analyze'),
);

request.files.add(
await http.MultipartFile.fromPath(
'file',
_image!.path,
contentType: MediaType('image', 'jpeg'),
),
);

// Добавляем
токен
авторизации
если
нужно \
// request.headers['Authorization'] = 'Bearer YOUR_TOKEN';

final
response = await request.send();
final
responseData = await response.stream.bytesToString();
final
data = json.decode(responseData);

if (response.statusCode == 200)
{
    setState(()
{
    _taskId = data['task_id'];
});
_pollTaskStatus();
} else {
    setState(()
{
    _result = {'error': data['detail'] ?? 'Upload failed'};
_isLoading = false;
});
}
} catch(e)
{
    setState(()
{
    _result = {'error': e.toString()};
_isLoading = false;
});
}
}

void
_pollTaskStatus()
{
_pollTimer?.cancel();
_pollTimer = Timer.periodic(const
Duration(seconds: 2), (timer) async {
if (_taskId == null)
{
    timer.cancel();
return;
}

try {
final response = await http.get(
Uri.parse('http://YOUR_SERVER_IP:8000/api/v1/task/$_taskId'),
// headers: {'Authorization': 'Bearer YOUR_TOKEN'},
);

if (response.statusCode == 200) {
final data = json.decode(response.body);
if (data['status'] == 'success') {
setState(() {
_result = data['result'];
_isLoading = false;
});
timer.cancel();
} else if (data['status'] == 'failure') {
setState(() {
_result = {'error': data['error']};
_isLoading = false;
});
timer.cancel();
}
// Если
still
pending / processing - продолжаем
опрашивать
}
} catch(e)
{
// Ошибка
сети - остановим
опрос
timer.cancel();
}
});
}

@override


void
dispose()
{
    _pollTimer?.cancel();
super.dispose();
}

@override


Widget
build(BuildContext
context) {
return Scaffold(
    appBar: AppBar(title: const
Text('Анализ еды по фото')),
body: Padding(
    padding: const
EdgeInsets.all(16.0),
child: Column(
    children: [
if (_image != null)
Container(
    height: 200,
decoration: BoxDecoration(
    border: Border.all(color: Colors.grey),
borderRadius: BorderRadius.circular(8),
),
child: Image.file(_image!, fit: BoxFit.contain),
),
const
SizedBox(height: 20),
Row(
    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
children: [
    ElevatedButton.icon(
        onPressed: () = > _pickImage(ImageSource.camera),
icon: const
Icon(Icons.camera_alt),
label: const
Text('Камера'),
),
ElevatedButton.icon(
    onPressed: () = > _pickImage(ImageSource.gallery),
icon: const
Icon(Icons.photo_library),
label: const
Text('Галерея'),
),
],
),
const
SizedBox(height: 20),
if (_isLoading)
const Column(
children: [
    CircularProgressIndicator(),
    SizedBox(height: 10),
Text('Анализируем...'),
],
),
if (_result != null & & _result!.containsKey('error'))
Card(
color: Colors.red[50],
child: Padding(
    padding: const
EdgeInsets.all(16.0),
child: Text(
    'Ошибка: ${_result!['
error
']}',
style: const
TextStyle(color: Colors.red),
),
),
),
if (_result != null & & !_result!.containsKey('error'))
Expanded(
child: SingleChildScrollView(
    child: Card(
    child: Padding(
    padding: const
EdgeInsets.all(16.0),
child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
children: [
    Text(
        _result!['food'],
style: Theme.of(context).textTheme.headlineSmall,
),
const
SizedBox(height: 10),
_buildRow('Вес:', '${_result!['
weight_g
']} г'),
_buildRow('Калории:', '${_result!['
calories
']} ккал'),
_buildRow('Белки:', '${_result!['
protein_g
']} г'),
_buildRow('Жиры:', '${_result!['
fat_g
']} г'),
_buildRow('Углеводы:', '${_result!['
carbs_g
']} г'),
const
SizedBox(height: 10),
LinearProgressIndicator(
    value: _result!['confidence'],
backgroundColor: Colors.grey[200],
valueColor: AlwaysStoppedAnimation < Color > (
    _result!['confidence'] > 0.8
? Colors.green
: _result!['confidence'] > 0.5
? Colors.orange
: Colors.red,
),
),
const
SizedBox(height: 5),
Text(
    'Уверенность: ${(_result!['
confidence
'] * 100).toStringAsFixed(0)}%',
style: const
TextStyle(fontSize: 12),
),
if (_result!['note'] != null)...[
    const SizedBox(height: 10),
Text(
    'Примечание: ${_result!['
note
']}',
style: const
TextStyle(fontStyle: FontStyle.italic),
),
],
],
),
),
),
),
),
],
),
),
);
}

Widget
_buildRow(String
label, String
value) {
return Padding(
    padding: const
EdgeInsets.symmetric(vertical: 4.0),
child: Row(
    mainAxisAlignment: MainAxisAlignment.spaceBetween,
children: [
    Text(label, style: const
TextStyle(fontWeight: FontWeight.bold)),
Text(value),
],
),
);
}
}