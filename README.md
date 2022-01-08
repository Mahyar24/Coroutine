
This code is a Proof of Concept for having a grasp of how event loops works under the hood.
The main inspiration is from David Beazley talk (http://dabeaz.com).
Link to the talk: https://youtu.be/Y4Gt3Xjd7G8. It's awesome.
It's worth to mention that all of the magic is happening by the select library.
Read the docs about it. https://docs.python.org/3/library/select.html
this code must NOT used for production.
Look at the 'server_example.py' and other files for watching this module in use.
Compatible with python3.9+. No third-party library is required, implemented in pure python.
This piece of code is a POC, (but a powerful minimalistic one!)
so it's not gonna follow community (PEP) and pylint principals/recommendations strictly. *
Mahyar@Mahyar24.com, Sat 19 Oct 2019.
