#!/usr/local/bin/expect -f
spawn ssh USERID@172.19.100.110
expect {
      "*sword:" {
           send -- "PASSW0RD\r"
      }
      "*yes/no" {
           send -- "yes\r"
           exp_continue
       }
      timeout {
           puts "Error - Fail to login\n"
	   exit 1
           # puts $expect_out(buffer)
       }
}
expect {
        "system>" {
                puts "<<---- Start Command OutPut ---->>\n"
                send "info -T system:blade[4]\r"
        }
        timeout {
           puts "Error - Fail to run command\n"
           exit 1
       }
}
expect {
        "system>" {
                puts "\n<<---- End Command OutPut ---->>\n"
        }
        timeout {
           puts "Error - Fail to run command\n"
           exit 1
       }
}
exit 0