from __future__ import absolute_import, unicode_literals
import base64
import json
import time
import threading
import datetime
import threading
import io

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.core.files.images import ImageFile
from django.core.exceptions import ObjectDoesNotExist

#from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import serializers, viewsets
from rest_framework import status

import requests


from .models import Camera, Stream, Image, Location, Project, Part, Annotation, Setting, Train

from vision_on_edge.settings import TRAINING_KEY, ENDPOINT, IOT_HUB_CONNECTION_STRING, DEVICE_ID, MODULE_ID

# FIXME move these to views
from azure.cognitiveservices.vision.customvision.training import CustomVisionTrainingClient
from azure.cognitiveservices.vision.customvision.training.models import ImageFileCreateEntry, Region

from azure.iot.device import IoTHubModuleClient
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import Twin, TwinProperties
try:
    iot = IoTHubRegistryManager(IOT_HUB_CONNECTION_STRING)
except:
    iot = None

def is_edge():
    try:
        IoTHubModuleClient.create_from_edge_environment()
        return True
    except:
        return False

def inference_module_url():
    if is_edge(): return '172.18.0.1:5000'
    else: return 'localhost:5000'

trainer = CustomVisionTrainingClient(TRAINING_KEY, endpoint=ENDPOINT)

is_trainer_valid = True

# Classification, General (compact) for classiciation
try:
    obj_detection_domain = next(domain for domain in trainer.get_domains() if domain.type == "ObjectDetection" and domain.name == "General (compact)")
except:
    is_trainer_valid = False


def export_iterationv3_2(project_id, iteration_id):
    url = ENDPOINT+'customvision/v3.2/training/projects/'+project_id+'/iterations/'+iteration_id+'/export?platform=ONNX'
    res = requests.post(url, '{body}', headers={'Training-key': TRAINING_KEY})

    return res


def update_train_status(project_id):
    def _train_status_worker(project_id):
        while True:
            time.sleep(1)
            project_obj = Project.objects.get(pk=project_id)
            camera_id = project_obj.camera_id
            customvision_project_id = project_obj.customvision_project_id
            camera = Camera.objects.get(pk=camera_id)

            iterations = trainer.get_iterations(customvision_project_id)
            if len(iterations) == 0:
                print('Training Status : Preparing')
                # @FIXME (Hugh): wrap it up
                obj, created = Train.objects.update_or_create(
                    project=project_obj,
                    defaults={'status': 'Training Status : Preparing', 'log': '', 'project':project_obj}
                )
                continue
                #return JsonResponse({'status': 'waiting training'})

            iteration = iterations[0]
            if iteration.exportable == False or iteration.status != 'Completed':
                print('Training Status : On-going')
                # @FIXME (Hugh): wrap it up
                obj, created = Train.objects.update_or_create(
                    project=project_obj,
                    defaults={'status': 'Training Status : On-going', 'log': '', 'project':project_obj}
                )
                continue
                #return JsonResponse({'status': 'waiting training'})

            exports = trainer.get_exports(customvision_project_id, iteration.id)
            if len(exports) == 0 or not exports[0].download_uri:
                print('Training Status : Exporting')
                # @FIXME (Hugh): wrap it up
                obj, created = Train.objects.update_or_create(
                    project=project_obj,
                    defaults={'status': 'Training Status : Exporting', 'log': '', 'project':project_obj}
                )
                #trainer.export_iteration(customvision_project_id, iteration.id, 'ONNX')
                res = export_iterationv3_2(customvision_project_id, iteration.id)
                print(res.json())
                continue
                #return JsonResponse({'status': 'exporting'})

            project_obj.download_uri = exports[0].download_uri
            project_obj.save(update_fields=['download_uri'])

            if exports[0].download_uri != None and len(exports[0].download_uri) > 0:
                update_twin(iteration.id, exports[0].download_uri, camera.rtsp)

            print('Training Status : Completed')
            # @FIXME (Hugh): wrap it up
            obj, created = Train.objects.update_or_create(
                    project=project_obj,
                    defaults={'status': 'ok', 'log': '', 'project':project_obj}
            )
            break
            #return JsonResponse({'status': 'ok', 'download_uri': exports[-1].download_uri})

    threading.Thread(target=_train_status_worker, args=(project_id,)).start()


@api_view()
def export(request, project_id):
    """get the status of train job sent to custom vision

       @FIXME (Hugh): change the naming of this endpoint
    """
    project_obj = Project.objects.get(pk=project_id)
    train_obj = Train.objects.get(project_id=project_id)

    return JsonResponse({'status': train_obj.status, 'download_uri': project_obj.download_uri})

# FIXME tmp workaround
@api_view()
def export_null(request):
    project_obj = Project.objects.all()[0]

    camera_id = project_obj.camera_id
    camera = Camera.objects.get(pk=camera_id)

    customvision_project_id = project_obj.customvision_project_id

    iterations = trainer.get_iterations(customvision_project_id)
    if len(iterations) == 0:
        print('not yet training ...')
        return JsonResponse({'status': 'waiting training'})

    iteration = iterations[0]

    if iteration.exportable == False or iteration.status != 'Completed':
        print('waiting training ...')
        return JsonResponse({'status': 'waiting training'})

    exports = trainer.get_exports(customvision_project_id, iteration.id)
    if len(exports) == 0:
        print('exporting ...')
        #trainer.export_iteration(customvision_project_id, iteration.id, 'ONNX')
        res = export_iterationv3_2(customvision_project_id, iteration.id)
        print(res.json())
        return JsonResponse({'status': 'exporting'})

    project_obj.download_uri = exports[0].download_uri
    project_obj.save(update_fields=['download_uri'])

    if exports[0].download_uri != None and len(exports[0].download_uri) > 0:
        update_twin(iteration.id, exports[0].download_uri, camera.rtsp)

    return JsonResponse({'status': 'ok', 'download_uri': exports[-1].download_uri})



#
# Part Views
#
class PartSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Part
        fields = ['id', 'name', 'description']

class PartViewSet(viewsets.ModelViewSet):
    queryset = Part.objects.all()
    serializer_class = PartSerializer

#
# Location Views
#
class LocationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'description', 'coordinates']

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
#
# Camera Views
#

class CameraSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Camera
        fields = ['id', 'name', 'rtsp']

class CameraViewSet(viewsets.ModelViewSet):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer


#
# Settings Views
#
class SettingSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Setting
        fields = [
            'id',
            'training_key',
            'endpoint',
            'iot_hub_connection_string',
            'device_id',
            'module_id'
        ]

class SettingViewSet(viewsets.ModelViewSet):
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer

#
# Projects Views
#
class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Project
        fields = [
            'id',
            'camera',
            'location',
            'parts',
            'download_uri',
            'needRetraining',
            'accuracyRangeMin',
            'accuracyRangeMax',
            'maxImages'
        ]
        extra_kwargs = {'download_uri': {'required': False}}


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

#
# Image Views
#
class ImageSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Image
        fields = ['id', 'image', 'labels', 'part', 'is_relabel', 'confidence']

class ImageViewSet(viewsets.ModelViewSet):
    queryset = Image.objects.all()
    serializer_class = ImageSerializer


#
# Annotation Views
#
class AnnotationSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Annotation
        fields = ['id', 'image', 'labels']

class AnnotationViewSet(viewsets.ModelViewSet):
    queryset = Annotation.objects.all()
    serializer_class = AnnotationSerializer


#
# Train Views
#
class TrainSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Train
        fields = ['id', 'status', 'log', 'project']
class TrainViewSet(viewsets.ModelViewSet):
    queryset = Train.objects.all()
    serializer_class = TrainSerializer




#
# Stream Views
#
streams = []
@api_view()
def connect_stream(request):
    part_id = request.query_params.get('part_id')
    rtsp = request.query_params.get('rtsp') or '0'
    inference = (not not request.query_params.get('inference')) or False
    if part_id is None:
        return JsonResponse({'status': 'failed', 'reason': 'part_id is missing'})

    try:
        Part.objects.get(pk=int(part_id))
        s = Stream(rtsp, part_id=part_id, inference=inference)
        streams.append(s)
        return JsonResponse({'status': 'ok', 'stream_id': s.id})
    except ObjectDoesNotExist:
        return JsonResponse({'status': 'failed', 'reason': 'part_id doesnt exist'})


@api_view()
def disconnect_stream(request, stream_id):
    for i in range(len(streams)):
        stream = streams[i]
        if stream.id == stream_id:
            stream.close()
            return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'failed', 'reason': 'cannot find stream_id '+str(stream_id)})

def video_feed(request, stream_id):
    for i in range(len(streams)):
        stream = streams[i]
        if stream.id == stream_id:
                return StreamingHttpResponse(stream.gen(), content_type='multipart/x-mixed-replace;boundary=frame')

    return HttpResponse('<h1>Unknown Stream '+str(stream_id)+' </h1>')

def capture(request, stream_id):
    for i in range(len(streams)):
        stream = streams[i]
        if stream.id == stream_id:
            img_data = stream.get_frame()
            img_io = io.BytesIO(img_data)
            img = ImageFile(img_io)
            img.name = datetime.datetime.utcnow().isoformat() + '.jpg'
            print(stream)
            print(stream.part_id)
            img_obj = Image(image=img, part_id=stream.part_id)
            img_obj.save()
            img_serialized = ImageSerializer(img_obj, context={'request': request})
            print(img_serialized.data)

            return JsonResponse({'status': 'ok', 'image': img_serialized.data})

    return JsonResponse({'status': 'failed', 'reason': 'cannot find stream_id '+str(stream_id)})

def _train(project_id):
    project_obj = Project.objects.get(pk=project_id)
    customvision_project_id = project_obj.customvision_project_id

    # @FIXME (Hugh): wrap it up
    obj, created = Train.objects.update_or_create(
        project=project_obj,
        defaults={'status': 'Sending images and annotations', 'log': '', 'project':project_obj}
    )

    try:
        count = 10
        while count > 0:
            part_ids = [part.id for part in project_obj.parts.all()]
            if len(part_ids) > 0: break
            print('waiting parts...')
            time.sleep(1)
            count -= 1


        print(project_obj.id)
        print('_____>>>>', part_ids)
        images = Image.objects.filter(part_id__in=part_ids).all()
        img_entries = []

        tags = trainer.get_tags(customvision_project_id)
        tag_dict = {}
        for tag in tags:
            tag_dict[tag.name] = tag.id

        for image_obj in images:
            print('*** image', image_obj)

            part = image_obj.part
            part_name = part.name
            if part_name not in tag_dict:
                print('part_name', part_name)
                tag = trainer.create_tag(customvision_project_id, part_name)
                tag_dict[tag.name] = tag.id

            tag_id = tag_dict[part_name]

            name = 'img-' + datetime.datetime.utcnow().isoformat()
            regions = []
            width = image_obj.image.width
            height = image_obj.image.height
            try:
                labels = json.loads(image_obj.labels)
                for label in labels:
                    x = label['x1'] / width
                    y = label['y1'] / height
                    w = (label['x2'] - label['x1']) / width
                    h = (label['y2'] - label['y1']) / height
                    region = Region(tag_id=tag_id, left=x, top=y, width=w, height=h)
                    regions.append(region)

                image = image_obj.image
                image.open()
                img_entry = ImageFileCreateEntry(name=name, contents=image.read(), regions=regions)
                img_entries.append(img_entry)
            except:
                pass
        print('uploading...')
        upload_result = trainer.create_images_from_files(customvision_project_id, images=img_entries)
        print('batch success:', upload_result.is_batch_successful)
        #print(upload_result)

        print('training...')
        trainer.train_project(customvision_project_id)

        print('start working status')
        update_train_status(project_id)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        print(f'Exception: {e}')
        return JsonResponse({'status': f'failed: {str(e)}'})

        # @FIXME (Hugh): wrap it up
        obj, created = Train.objects.update_or_create(
            project=project_obj,
            defaults={'status': 'Training Status : Preparing', 'log': '', 'project':project_obj}
        )

@api_view()
def train(request, project_id):
    print('sleeping')
    return _train(project_id)



# FIXME will need to find a better way to deal with this
iteration_ids = set([])
def update_twin(iteration_id, download_uri, rtsp):

    if iot is None: return

    if iteration_id in iteration_ids:
        print('[INFO] This iteration already deployed in the Edge')
        return

    try:
        module = iot.get_module(DEVICE_ID, MODULE_ID)
    except:
        print('[ERROR] module does not exist', DEVICE_ID, MODULE_ID)
        return

    twin = Twin()
    twin.properties = TwinProperties(desired={
        'inference_files_zip_url': download_uri,
        'cam_type': 'rtsp_stream',
        'cam_source': rtsp
    })

    iot.update_module_twin(DEVICE_ID, MODULE_ID, twin, module.etag)

    print('[INFO] Updated IoT Module Twin with uri and rtsp', download_uri, rtsp)

    iteration_ids.add(iteration_id)

@api_view(['POST'])
def upload_relabel_image(request):
    part_name = request.data['part_name']
    labels = request.data['labels']
    img_data = base64.b64decode(request.data['img'])
    confidence = request.data['confidence']
    is_relabel = request.data['is_relabel']

    parts = Part.objects.filter(name=part_name)
    if len(parts) == 0:
        print('[ERROR] Unknown Part Name', part_name)
        return JsonResponse({'status': 'failed'})


    img_io = io.BytesIO(img_data)

    img = ImageFile(img_io)
    img.name = datetime.datetime.utcnow().isoformat() + '.jpg'
    img_obj = Image(image=img, part_id=parts[0].id, labels=labels, confidence=confidence, is_relabel=True)
    img_obj.save()

    return JsonResponse({'status': 'ok'})
