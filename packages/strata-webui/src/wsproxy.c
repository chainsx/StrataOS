#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <openssl/evp.h>
#include <openssl/sha.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#define LIMIT 65536

static int write_all(int fd, const void *data, size_t len) {
    const unsigned char *p = data;
    while (len) { ssize_t n = write(fd, p, len); if (n < 0 && errno == EINTR) continue; if (n <= 0) return -1; p += n; len -= (size_t)n; }
    return 0;
}

static char *trim(char *s) { while (*s == ' ' || *s == '\t') s++; char *e=s+strlen(s); while(e>s && (e[-1]=='\r'||e[-1]=='\n'||e[-1]==' '||e[-1]=='\t')) *--e=0; return s; }

static int session_valid(const char *directory, const char *token) {
    if(strlen(token)!=64)return 0;
    for(const unsigned char *p=(const unsigned char *)token;*p;p++)
        if(!((*p>='0'&&*p<='9')||(*p>='a'&&*p<='f')||(*p>='A'&&*p<='F')))return 0;
    char path[512],line[256],*end;unsigned long long expires;
    if(snprintf(path,sizeof(path),"%s/%s",directory,token)>=(int)sizeof(path))return 0;
    FILE *f=fopen(path,"r");if(!f)return 0;if(!fgets(line,sizeof(line),f)){fclose(f);return 0;}fclose(f);
    errno=0;expires=strtoull(line,&end,10);
    return !errno&&end!=line&&(*end=='\t'||*end==' ')&&expires>(unsigned long long)time(NULL);
}

static int connect_backend(const char *spec) {
    char host[128], *colon; unsigned long port; snprintf(host,sizeof(host),"%s",spec); colon=strrchr(host,':'); if(!colon)return -1; *colon++=0; port=strtoul(colon,0,10);
    int fd=socket(AF_INET,SOCK_STREAM,0); struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons((uint16_t)port)}; if(fd<0||inet_pton(AF_INET,host,&a.sin_addr)!=1||connect(fd,(void*)&a,sizeof(a))<0){if(fd>=0)close(fd);return -1;} return fd;
}

static int handshake(int fd, const char *session_dir, char session[256]) {
    char req[LIMIT+1], key[256]="", supplied[129]=""; size_t used=0;
    while(used<LIMIT){ssize_t n=read(fd,req+used,LIMIT-used);if(n<=0)return -1;used+=(size_t)n;req[used]=0;if(strstr(req,"\r\n\r\n"))break;}
    char *first=strtok(req,"\r\n"), *line; if(!first||strncmp(first,"GET ",4))return -1;
    char *q=strstr(first,"token="); if(q){q+=6;size_t n=strcspn(q," &");if(n<sizeof(supplied)){memcpy(supplied,q,n);supplied[n]=0;}}
    q=strstr(first,"session="); if(q){q+=8;size_t n=strcspn(q," &");if(n<256){memcpy(session,q,n);session[n]=0;}}
    while((line=strtok(NULL,"\r\n"))){if(!strncasecmp(line,"Sec-WebSocket-Key:",18))snprintf(key,sizeof(key),"%s",trim(line+18));}
    if(!key[0]||!session_valid(session_dir,supplied))return -1;
    char input[512], accept[128]; unsigned char digest[SHA_DIGEST_LENGTH];
    snprintf(input,sizeof(input),"%s258EAFA5-E914-47DA-95CA-C5AB0DC85B11",key); SHA1((unsigned char*)input,strlen(input),digest);
    EVP_EncodeBlock((unsigned char*)accept,digest,SHA_DIGEST_LENGTH);
    char response[512];int n=snprintf(response,sizeof(response),"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n",accept);
    return write_all(fd,response,(size_t)n);
}

static int session_backend(const char *directory, const char *session, char backend[128]) {
    char path[512], value[32];
    if(!session[0]||strlen(session)>200)return -1;
    for(const unsigned char *p=(const unsigned char *)session;*p;p++)
        if(!((*p>='A'&&*p<='Z')||(*p>='a'&&*p<='z')||(*p>='0'&&*p<='9')||*p=='.'||*p=='_'||*p=='-'))return -1;
    if(snprintf(path,sizeof(path),"%s/%s/vnc-port",directory,session)>=(int)sizeof(path))return -1;
    FILE *f=fopen(path,"r");if(!f)return -1;if(!fgets(value,sizeof(value),f)){fclose(f);return -1;}fclose(f);
    char *end=0;unsigned long port=strtoul(value,&end,10);if(end==value||(*end&&*end!='\n')||port<5900||port>5999)return -1;
    snprintf(backend,128,"127.0.0.1:%lu",port);return 0;
}

static int ws_send(int fd, unsigned opcode, const unsigned char *data, size_t len) {
    unsigned char h[10];size_t n=0;h[n++]=(unsigned char)(0x80|opcode);if(len<126)h[n++]=(unsigned char)len;else if(len<=65535){h[n++]=126;h[n++]=(unsigned char)(len>>8);h[n++]=(unsigned char)len;}else{h[n++]=127;for(int i=7;i>=0;i--)h[n++]=(unsigned char)((uint64_t)len>>(i*8));}
    return write_all(fd,h,n)||write_all(fd,data,len);
}

static int proxy_loop(int client, int backend) {
    unsigned char in[LIMIT], raw[LIMIT];size_t have=0;
    for(;;){struct pollfd p[2]={{client,POLLIN,0},{backend,POLLIN,0}};if(poll(p,2,-1)<0){if(errno==EINTR)continue;return -1;}
        if(p[1].revents&POLLIN){ssize_t n=read(backend,raw,sizeof(raw));if(n<=0)return 0;if(ws_send(client,2,raw,(size_t)n)<0)return -1;}
        if(p[0].revents&POLLIN){ssize_t n=read(client,in+have,sizeof(in)-have);if(n<=0)return 0;have+=(size_t)n;
            while(have>=2){size_t pos=2;uint64_t len=in[1]&127;unsigned op=in[0]&15;if(len==126){if(have<4)break;len=((uint64_t)in[2]<<8)|in[3];pos=4;}else if(len==127){if(have<10)break;len=0;for(int i=0;i<8;i++)len=(len<<8)|in[2+i];pos=10;}if(!(in[1]&128)||len>LIMIT)return -1;if(have<pos+4+len)break;unsigned char *mask=in+pos;pos+=4;for(uint64_t i=0;i<len;i++)in[pos+i]^=mask[i&3];if(op==8)return 0;if(op==9){if(ws_send(client,10,in+pos,(size_t)len)<0)return -1;}else if(op==2||op==0){if(write_all(backend,in+pos,(size_t)len)<0)return -1;}size_t used=pos+(size_t)len;memmove(in,in+used,have-used);have-=used;}
        }}
}

static void serve(int client,const char *configured_backend,const char *session_dir,const char *auth_dir){const char *forbidden="HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n";char session[256]="",dynamic_backend[128];if(handshake(client,auth_dir,session)<0){write_all(client,forbidden,strlen(forbidden));return;}const char *backend=configured_backend;if(session_dir){if(session_backend(session_dir,session,dynamic_backend)<0){write_all(client,forbidden,strlen(forbidden));return;}backend=dynamic_backend;}int fd=-1;for(int attempt=0;attempt<150&&fd<0;attempt++){fd=connect_backend(backend);if(fd<0)poll(NULL,0,100);}if(fd<0)return;proxy_loop(client,fd);close(fd);}

int main(int argc,char **argv){int port=6080,opt;const char *backend="127.0.0.1:5900",*session_dir=NULL,*auth_dir="/run/strata-webui/auth-sessions",*listen_address=NULL;while((opt=getopt(argc,argv,"l:b:d:t:i:"))!=-1){if(opt=='l')port=atoi(optarg);else if(opt=='b')backend=optarg;else if(opt=='d')session_dir=optarg;else if(opt=='t')auth_dir=optarg;else if(opt=='i')listen_address=optarg;else return 2;}signal(SIGCHLD,SIG_IGN);signal(SIGPIPE,SIG_IGN);int s,one=1;if(listen_address){s=socket(AF_INET,SOCK_STREAM,0);if(s>=0)setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));struct sockaddr_in a={.sin_family=AF_INET,.sin_port=htons((uint16_t)port)};if(s<0||inet_pton(AF_INET,listen_address,&a.sin_addr)!=1||bind(s,(void*)&a,sizeof(a))<0||listen(s,32)<0){perror("strata-wsproxy");if(s>=0)close(s);return 1;}}else{s=socket(AF_INET6,SOCK_STREAM,0);if(s>=0){setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one));int off=0;setsockopt(s,IPPROTO_IPV6,IPV6_V6ONLY,&off,sizeof(off));}struct sockaddr_in6 a={.sin6_family=AF_INET6,.sin6_port=htons((uint16_t)port),.sin6_addr=IN6ADDR_ANY_INIT};if(s<0||bind(s,(void*)&a,sizeof(a))<0||listen(s,32)<0){perror("strata-wsproxy");if(s>=0)close(s);return 1;}}for(;;){int c=accept(s,0,0);if(c<0){if(errno==EINTR)continue;return 1;}pid_t p=fork();if(p==0){close(s);serve(c,backend,session_dir,auth_dir);close(c);_exit(0);}close(c);} }
