#define _GNU_SOURCE
#include <sys/prctl.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    prctl(PR_SET_NAME,argv[1],0,0,0);
    if(!strcmp(argv[1],"apache")) signal(SIGTERM,SIG_IGN);
    for(;;)pause();
}
