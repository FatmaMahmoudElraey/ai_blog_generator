from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
from pytube import YouTube
import os
import assemblyai as aai
from .models import BlogPost
import yt_dlp
import requests
import cohere

from dotenv import load_dotenv
load_dotenv()


@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
                 # get yt title
            title = yt_title(yt_link)

        # get transcript
            transcription = get_transcription(yt_link)
            if not transcription:
                return JsonResponse({'error': " Failed to get transcript"}, status=500)


        # use OpenAI to generate the blog
            blog_content = generate_blog_from_transcription(transcription)
            if not blog_content:
                return JsonResponse({'error': " Failed to generate blog article"}, status=500)

        # save blog article to database
            new_blog_article = BlogPost.objects.create(
                user=request.user,
                youtube_title=title,
                youtube_link=yt_link,
                generated_content=blog_content,
            )
            new_blog_article.save()

        # return blog article as a response
            return JsonResponse({'content': blog_content})

        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)


       
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)


def yt_title(link):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(link, download=False)
            return info.get('title', 'Unknown Title')
    except Exception as e:
        print(f"Error fetching title: {e}")
        return "Unknown Title"


import os
from yt_dlp import YoutubeDL

def download_audio(link):
    try:
        download_dir = 'downloads'
        os.makedirs(download_dir, exist_ok=True)

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'quiet': True
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            file_ext = info['ext']
            file_path = os.path.join(download_dir, f"{info['title']}.{file_ext}")

        print(f"Downloaded audio file at: {file_path}")
        return file_path

    except Exception as e:
        print(f"Error downloading audio: {e}")
        return None

def get_transcription(link):
    audio_file = download_audio(link)
    if not audio_file:
        return None

    aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")  

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    # Delete audio after transcription
    try:
        os.remove(audio_file)
        print(f"Deleted file: {audio_file}")
    except Exception as e:
        print(f"Error deleting file: {e}")
    print(transcript.text)
    return transcript.text

# def get_transcription(link):
#     audio_file = download_audio(link)
#     aai.settings.api_key = "fc74550333b0427e9ee9faccc8e43fed"

#     transcriber = aai.Transcriber()
#     transcript = transcriber.transcribe(audio_file)

#     return transcript.text


# def generate_blog_from_transcription(transcription):
    response = requests.post('http://localhost:11434/api/generate', json={
        'model': 'mistral:7b-instruct',
        'prompt': f'Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but don\'t make it look like a YouTube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:',
        'temperature': 0.7,
        'top_p': 0.9,
        'stream': False
    })

    if response.status_code == 200:
        data = response.json()
        blog_content = data.get('response')
        return blog_content
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return "Failed to generate blog content."


co = cohere.Client(os.getenv("COHERE_API_KEY")) 
def generate_blog_from_transcription(transcription):
    try:
        response = co.chat(
            model='command-nightly',
            message=f"Write a blog article based on this transcript. Do not mention it's from a video:\n\n{transcription}",
            temperature=0.7,
            max_tokens=500,
        )

        blog_content = response.text 
        return blog_content

    except Exception as e:
        print(f"Cohere Error: {e}")
        return None

def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})
        
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})
        
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')

